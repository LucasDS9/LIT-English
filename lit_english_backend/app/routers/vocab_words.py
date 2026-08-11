"""
Rotas de "Aprender" (treino de vocabulário por reconhecimento/múltipla escolha):
- Professor: criar, listar, editar e excluir palavras (com atribuição por aluno)
- Aluno: aprender palavras — sempre 4 opções (a certa + 3 distratores
  cadastrados pelo professor), com progresso Nova / Em revisão / Aprendida

A pronúncia da palavra (botão embaixo do card) e o popup de "clicar numa
palavra da frase para ver o significado" NÃO precisam de rotas novas:
- Pronúncia: reutiliza GET /tts/speak?text=<palavra> (mesmo endpoint já
  usado em Revisar e no popup de vocabulário do Read and Listen) — o
  frontend só precisa chamar com a palavra isolada, não a frase inteira.
- Popup de significado: reutiliza POST /texts/word-lookup (mesmo endpoint do
  Read and Listen), sem enviar text_id. O único cuidado é no FRONTEND: a
  própria palavra sendo aprendida não deve ficar clicável na frase de
  exemplo (ou o clique não deve disparar o lookup pra ela), pra não entregar
  a resposta da múltipla escolha. Este backend já ajuda nisso devolvendo,
  na fila de aprendizado, só a palavra + as opções embaralhadas — nunca qual
  delas é a certa (isso só sai em /vocab-words/learn/{word_id}, depois que o
  aluno responde).
"""
import random
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.models import (
    AccessType,
    User,
    UserRole,
    VocabWord,
    VocabWordAssignment,
    VocabWordProgress,
    VocabWordStatus,
)
from app.schemas import (
    VocabLearnCardOut,
    VocabLearnQueueOut,
    VocabLearnResult,
    VocabLearnSubmit,
    VocabWordCreate,
    VocabWordOut,
    VocabWordProgressOut,
    VocabWordUpdate,
)

router = APIRouter(prefix="/vocab-words", tags=["Aprender"])

# Card é considerado "aprendida" depois desse número de acertos seguidos.
LEARNED_STREAK = 3

# Estrutura do ciclo diário de aprendizado (tela "Aprender"), sempre
# CONTÍNUA (um bloco emenda no outro, sem esperar o aluno pedir "próximo
# ciclo" — só aparece a tela de "concluiu o ciclo" no final de tudo):
#   1) até 15 palavras NOVAS (nunca respondidas)
#   2) revisão de TODAS as palavras erradas que ficaram devidas agora
#      (status em_revisao, reaparecem na hora — não esperam as 15 novas
#      acabarem pra aparecer; é o próprio erro do aluno "voltando" pra ele
#      até acertar)
#   3) até 10 palavras ANTIGAS pra revisão geral — de qualquer status/idade
#      (em_revisao ainda não devida ou já aprendida), desde que o aluno já
#      tenha respondido alguma vez e a palavra não esteja em (1) ou (2).
#      Se não houver nenhuma disponível, esse bloco simplesmente não entra
#      no ciclo (sem erro, sem espaço vazio).
#   4) até 5 palavras já APRENDIDAS, escolhidas aleatoriamente (podem ser de
#      ciclos anteriores), só pra reforçar retenção
# Cada chamada a /learn/next devolve o ciclo inteiro (ou o que houver
# disponível dele); quando o aluno termina os cards, o ciclo terminou.
NEW_WORDS_PER_CYCLE = 15
OLD_REVIEW_PER_CYCLE = 10
LEARNED_REVIEW_PER_CYCLE = 5

# Separador interno dos distratores (a tradução pode conter vírgula, então
# não usamos vírgula aqui).
_DISTRACTOR_SEP = "|"


def _validate_student_ids(student_ids: list[int], db: Session) -> None:
    found = (
        db.query(User.id)
        .filter(User.id.in_(student_ids), User.role == UserRole.aluno)
        .count()
    )
    if found != len(set(student_ids)):
        raise HTTPException(status_code=404, detail="Um ou mais alunos selecionados não foram encontrados.")


def student_language(student: User) -> str:
    """
    A que língua-alvo um aluno pertence, pra fins de conteúdo "nativo":
    - Curso normal (access_type=padrao): sempre "ingles".
    - Acesso Especial (access_type=especial): a língua escolhida no
      cadastro (target_language) — ex.: "italiano".
    """
    if student.access_type == AccessType.especial and student.target_language:
        return student.target_language.strip().lower()
    return "ingles"


def _all_approved_student_ids_for_language(language: str, db: Session) -> list[int]:
    language = (language or "ingles").strip().lower()
    students = (
        db.query(User)
        .filter(User.role == UserRole.aluno, User.is_approved.is_(True))
        .all()
    )
    return [s.id for s in students if student_language(s) == language]


def _resolve_student_ids(student_ids: list[int] | None, language: str, db: Session) -> list[int]:
    """Sem `student_ids`, a palavra fica nativa: vai pra todos os alunos
    aprovados agora cuja língua bate com `language` (e os aprovados depois
    recebem via approve_student)."""
    if not student_ids:
        return _all_approved_student_ids_for_language(language, db)
    _validate_student_ids(student_ids, db)
    return student_ids


def _validate_example_or_tip(example_sentence: str | None, tip: str | None) -> tuple[str | None, str | None]:
    example_sentence = (example_sentence or "").strip() or None
    tip = (tip or "").strip() or None
    if not example_sentence and not tip:
        raise HTTPException(
            status_code=422,
            detail="Informe uma frase de exemplo (example_sentence) ou uma dica (tip).",
        )
    return example_sentence, tip


def _validate_distractors(distractors: list[str], translation: str) -> list[str]:
    cleaned = [d.strip() for d in distractors if d.strip()]
    if len(cleaned) != 3:
        raise HTTPException(status_code=422, detail="Informe exatamente 3 opções erradas (distratores).")
    if any(d.lower() == translation.strip().lower() for d in cleaned):
        raise HTTPException(
            status_code=422,
            detail="Um dos distratores é igual à tradução correta — as 4 opções precisam ser diferentes.",
        )
    return cleaned


def _pack_distractors(distractors: list[str]) -> str:
    return _DISTRACTOR_SEP.join(distractors)


def _unpack_distractors(raw: str) -> list[str]:
    return [d for d in raw.split(_DISTRACTOR_SEP) if d]


def _to_word_out(word: VocabWord) -> VocabWordOut:
    return VocabWordOut(
        id=word.id,
        word=word.word,
        part_of_speech=word.part_of_speech,
        translation=word.translation,
        example_sentence=word.example_sentence,
        tip=word.tip,
        distractors=_unpack_distractors(word.distractors),
        explanation=word.explanation,
        language=word.language,
        created_at=word.created_at,
        students=[{"id": s.id, "name": s.name} for s in word.students],
    )


# ============================================================
# PROFESSOR: CRUD de palavras
# ============================================================

@router.post("", response_model=VocabWordOut, status_code=status.HTTP_201_CREATED)
def create_vocab_word(
    data: VocabWordCreate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    language = (data.language or "ingles").strip().lower()
    student_ids = _resolve_student_ids(data.student_ids, language, db)
    if not student_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum aluno aprovado encontrado para atribuir a palavra (língua: {language}).",
        )
    distractors = _validate_distractors(data.distractors, data.translation)
    example_sentence, tip = _validate_example_or_tip(data.example_sentence, data.tip)

    word = VocabWord(
        word=data.word.strip(),
        part_of_speech=data.part_of_speech.strip(),
        translation=data.translation.strip(),
        example_sentence=example_sentence,
        tip=tip,
        distractors=_pack_distractors(distractors),
        explanation=(data.explanation or "").strip() or None,
        language=language,
    )
    db.add(word)
    db.flush()

    for student_id in set(student_ids):
        db.add(VocabWordAssignment(word_id=word.id, student_id=student_id))

    db.commit()
    db.refresh(word)
    return _to_word_out(word)


@router.get("", response_model=list[VocabWordOut])
def list_vocab_words(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista todas as palavras cadastradas (visão do professor)."""
    words = db.query(VocabWord).order_by(VocabWord.created_at.desc()).all()
    return [_to_word_out(w) for w in words]


@router.put("/{word_id}", response_model=VocabWordOut)
def update_vocab_word(
    word_id: int,
    data: VocabWordUpdate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    word = db.query(VocabWord).filter(VocabWord.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Palavra não encontrada.")

    if data.word is not None:
        word.word = data.word.strip()
    if data.part_of_speech is not None:
        word.part_of_speech = data.part_of_speech.strip()
    if data.example_sentence is not None:
        word.example_sentence = data.example_sentence.strip() or None
    if data.tip is not None:
        word.tip = data.tip.strip() or None
    if data.explanation is not None:
        word.explanation = data.explanation.strip() or None
    if not (word.example_sentence or word.tip):
        raise HTTPException(
            status_code=422,
            detail="Informe uma frase de exemplo (example_sentence) ou uma dica (tip).",
        )

    new_translation = data.translation.strip() if data.translation is not None else word.translation
    if data.distractors is not None:
        distractors = _validate_distractors(data.distractors, new_translation)
        word.distractors = _pack_distractors(distractors)
    elif data.translation is not None:
        # Tradução mudou mas os distratores não foram reenviados: garante
        # que nenhum distrator antigo ficou igual à nova tradução.
        _validate_distractors(_unpack_distractors(word.distractors), new_translation)
    if data.translation is not None:
        word.translation = new_translation

    if data.language is not None:
        word.language = data.language.strip().lower()

    if data.student_ids is not None:
        if len(data.student_ids) == 0:
            raise HTTPException(status_code=400, detail="Selecione ao menos um aluno.")
        _validate_student_ids(data.student_ids, db)
        db.query(VocabWordAssignment).filter(VocabWordAssignment.word_id == word.id).delete()
        for student_id in set(data.student_ids):
            db.add(VocabWordAssignment(word_id=word.id, student_id=student_id))

    db.commit()
    db.refresh(word)
    return _to_word_out(word)


@router.delete("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vocab_word(
    word_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    word = db.query(VocabWord).filter(VocabWord.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Palavra não encontrada.")

    db.query(VocabWordProgress).filter(VocabWordProgress.word_id == word_id).delete()
    db.delete(word)  # assignments somem via cascade da relationship
    db.commit()
    return None


# ============================================================
# ALUNO: sessão de aprendizado (múltipla escolha, sempre 4 opções)
# ============================================================

def _require_student(user: User) -> None:
    if user.role != UserRole.aluno:
        raise HTTPException(status_code=403, detail="Apenas alunos podem usar o treino de vocabulário.")


def _status_label(progress: VocabWordProgress | None) -> VocabWordStatus:
    return progress.status if progress else VocabWordStatus.nova


def _build_options(word: VocabWord) -> list[str]:
    options = [word.translation] + _unpack_distractors(word.distractors)
    random.shuffle(options)
    return options


@router.get("/learn/next", response_model=VocabLearnQueueOut)
def get_learn_queue(
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    Monta o próximo ciclo diário de aprendizado, sempre nesta ordem (um
    bloco emenda direto no próximo, ciclo contínuo):
      1) até 15 palavras novas (nunca respondidas)
      2) todas as palavras em revisão que já estão devidas agora (erradas
         recentemente — reaparecem na hora, não esperam as novas acabarem)
      3) até 10 palavras antigas pra revisão geral, de qualquer status/idade
         (desde que já tenham sido respondidas antes e não estejam nos
         blocos 1/2) — se não houver nenhuma, o bloco simplesmente não entra
      4) até 5 palavras já aprendidas (retenção; podem ser de ciclos
         anteriores), em ordem aleatória
    Cada card já vem com as 4 opções embaralhadas — nunca revela qual é a
    certa.
    """
    _require_student(student)
    now = datetime.utcnow()

    assigned_subquery = db.query(VocabWordAssignment.word_id).filter(
        VocabWordAssignment.student_id == student.id
    )
    attempted_subquery = db.query(VocabWordProgress.word_id).filter(
        VocabWordProgress.student_id == student.id
    )

    # 1) Novas: atribuídas ao aluno e sem nenhum progresso registrado ainda.
    new_words = (
        db.query(VocabWord)
        .filter(VocabWord.id.in_(assigned_subquery))
        .filter(~VocabWord.id.in_(attempted_subquery))
        .order_by(VocabWord.created_at.asc())
        .limit(NEW_WORDS_PER_CYCLE)
        .all()
    )

    # 2) Revisão: tudo que está "em_revisao" e já devido agora (inclui as
    # que acabaram de ser erradas nesta mesma sessão, que voltam na hora).
    review_words = (
        db.query(VocabWord)
        .join(VocabWordProgress, VocabWordProgress.word_id == VocabWord.id)
        .filter(VocabWordProgress.student_id == student.id)
        .filter(VocabWordProgress.status == VocabWordStatus.em_revisao)
        .filter(VocabWordProgress.next_review <= now)
        .order_by(VocabWordProgress.next_review.asc())
        .all()
    )

    # 3) Antigas para revisão geral: até 10 palavras já respondidas antes
    # (qualquer status/idade — em_revisao ainda não devida ou já aprendida),
    # que ainda não entraram nos blocos 1/2 acima. Se não sobrar nenhuma,
    # o bloco fica vazio e o ciclo segue direto pras concluídas — sem erro,
    # sem espaço em branco.
    already_in_cycle_ids = [w.id for w in new_words] + [w.id for w in review_words]
    old_review_words = (
        db.query(VocabWord)
        .join(VocabWordProgress, VocabWordProgress.word_id == VocabWord.id)
        .filter(VocabWordProgress.student_id == student.id)
        .filter(~VocabWord.id.in_(already_in_cycle_ids))
        .order_by(VocabWordProgress.last_reviewed.asc().nullsfirst())
        .limit(OLD_REVIEW_PER_CYCLE)
        .all()
    )

    # 4) Concluídas: reforço de retenção, aleatório, independente de estarem
    # devidas ou não (podem ser de ciclos anteriores).
    already_in_cycle_ids += [w.id for w in old_review_words]
    learned_words = (
        db.query(VocabWord)
        .join(VocabWordProgress, VocabWordProgress.word_id == VocabWord.id)
        .filter(VocabWordProgress.student_id == student.id)
        .filter(VocabWordProgress.status == VocabWordStatus.aprendida)
        .filter(~VocabWord.id.in_(already_in_cycle_ids))
        .order_by(func.random())
        .limit(LEARNED_REVIEW_PER_CYCLE)
        .all()
    )

    cycle_words = new_words + review_words + old_review_words + learned_words

    progress_by_word = {
        p.word_id: p
        for p in db.query(VocabWordProgress).filter(
            VocabWordProgress.student_id == student.id,
            VocabWordProgress.word_id.in_([w.id for w in cycle_words]),
        )
    }

    cards = [
        VocabLearnCardOut(
            word_id=w.id,
            word=w.word,
            part_of_speech=w.part_of_speech,
            example_sentence=w.example_sentence,
            tip=w.tip,
            options=_build_options(w),
            status=_status_label(progress_by_word.get(w.id)),
        )
        for w in cycle_words
    ]

    total_assigned = db.query(VocabWordAssignment).filter(VocabWordAssignment.student_id == student.id).count()
    total_learned = (
        db.query(VocabWordProgress)
        .filter(VocabWordProgress.student_id == student.id, VocabWordProgress.status == VocabWordStatus.aprendida)
        .count()
    )

    return VocabLearnQueueOut(cards=cards, total_assigned=total_assigned, total_learned=total_learned)


@router.post("/learn/{word_id}", response_model=VocabLearnResult)
def submit_learn_answer(
    word_id: int,
    payload: VocabLearnSubmit,
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """O aluno escolheu uma das 4 opções para esta palavra. Atualiza o status
    (Nova -> Em revisão -> Aprendida) e agenda a próxima revisão."""
    _require_student(student)

    word = db.query(VocabWord).filter(VocabWord.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Palavra não encontrada.")

    assigned = (
        db.query(VocabWordAssignment)
        .filter(VocabWordAssignment.word_id == word_id, VocabWordAssignment.student_id == student.id)
        .first()
    )
    if not assigned:
        raise HTTPException(status_code=403, detail="Esta palavra não está disponível para você.")

    is_correct = payload.selected_option.strip().lower() == word.translation.strip().lower()

    progress = (
        db.query(VocabWordProgress)
        .filter(VocabWordProgress.student_id == student.id, VocabWordProgress.word_id == word_id)
        .first()
    )
    if not progress:
        progress = VocabWordProgress(student_id=student.id, word_id=word_id)
        db.add(progress)
        db.flush()

    if is_correct:
        progress.correct_streak += 1
        progress.status = (
            VocabWordStatus.aprendida
            if progress.correct_streak >= LEARNED_STREAK
            else VocabWordStatus.em_revisao
        )
        # Espaçamento cresce a cada acerto seguido (1, 3, 7, 14... dias).
        days = {1: 1, 2: 3, 3: 7}.get(progress.correct_streak, 14)
    else:
        progress.correct_streak = 0
        # Errou: sempre volta para "Em revisão" (mesmo se já estava
        # "Aprendida") e reaparece logo, no mesmo espírito do SM-2.
        progress.status = VocabWordStatus.em_revisao
        days = 0  # reaparece ainda na mesma sessão/dia

    progress.last_reviewed = datetime.utcnow()
    progress.next_review = datetime.utcnow() + timedelta(days=days)

    db.commit()
    db.refresh(progress)

    return VocabLearnResult(
        correct=is_correct,
        correct_answer=word.translation,
        explanation=word.explanation,
        status=progress.status,
    )


# ============================================================
# PROFESSOR: vocabulário (Aprender) de um aluno específico
# ============================================================

@router.get("/vocabulary/{student_id}", response_model=list[VocabWordProgressOut])
def get_student_vocab_progress(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista as palavras atribuídas a um aluno, com o status atual (Nova /
    Em revisão / Aprendida)."""
    student = db.query(User).filter(User.id == student_id, User.role == UserRole.aluno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")

    rows = (
        db.query(VocabWord, VocabWordProgress)
        .join(VocabWordAssignment, VocabWordAssignment.word_id == VocabWord.id)
        .outerjoin(
            VocabWordProgress,
            (VocabWordProgress.word_id == VocabWord.id) & (VocabWordProgress.student_id == student_id),
        )
        .filter(VocabWordAssignment.student_id == student_id)
        .order_by(VocabWord.created_at.desc())
        .all()
    )

    now = datetime.utcnow()
    items = []
    for word, progress in rows:
        items.append(
            VocabWordProgressOut(
                word_id=word.id,
                word=word.word,
                part_of_speech=word.part_of_speech,
                translation=word.translation,
                status=_status_label(progress),
                next_review=progress.next_review if progress else now,
            )
        )
    return items
