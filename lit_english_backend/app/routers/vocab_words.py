"""
Rotas de "Aprender" (treino de vocabulário por reconhecimento/múltipla escolha):
- Professor: criar, listar, editar e excluir palavras (com atribuição por aluno)
- Aluno: aprender palavras NOVAS — sempre 4 opções (a certa + 3 distratores).
  Aprender exibe somente palavras nunca respondidas. O primeiro acerto gradua
  a palavra para Revisar como flashcard; a progressão de status acontece lá.
"""
import random
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai_judge import judge_answer
from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.flashcard_judge import judge_flashcard_answer
from app.models import (
    AccessType,
    CardProgress,
    Flashcard,
    FlashcardAssignment,
    ReviewCardStatus,
    ReviewMode,
    User,
    UserRole,
    VocabWord,
    VocabWordAssignment,
    VocabWordProgress,
    VocabWordStatus,
)
from app.schemas import (
    FlashcardPronunciationResult,
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

# Máximo de palavras novas por sessão de Aprender.
NEW_WORDS_PER_CYCLE = 15

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


def _graduate_word_to_review(word: VocabWord, student: User, db: Session) -> Flashcard:
    """Cria (ou reutiliza) o flashcard de Revisar e atribui ao aluno."""
    if word.review_flashcard_id:
        flashcard = db.query(Flashcard).filter(Flashcard.id == word.review_flashcard_id).first()
    else:
        flashcard = Flashcard(front=word.word, back=word.translation)
        db.add(flashcard)
        db.flush()
        word.review_flashcard_id = flashcard.id

    assigned = (
        db.query(FlashcardAssignment)
        .filter(
            FlashcardAssignment.flashcard_id == flashcard.id,
            FlashcardAssignment.student_id == student.id,
        )
        .first()
    )
    if not assigned:
        db.add(FlashcardAssignment(flashcard_id=flashcard.id, student_id=student.id))

    card_progress = (
        db.query(CardProgress)
        .filter(
            CardProgress.student_id == student.id,
            CardProgress.flashcard_id == flashcard.id,
        )
        .first()
    )
    if not card_progress:
        card_progress = CardProgress(
            student_id=student.id,
            flashcard_id=flashcard.id,
            review_status=ReviewCardStatus.aprendendo,
            review_mode=ReviewMode.flip,
            correct_streak=0,
            next_review=datetime.utcnow(),
        )
        db.add(card_progress)
    elif card_progress.review_status is None:
        card_progress.review_status = ReviewCardStatus.aprendendo
        card_progress.review_mode = ReviewMode.flip

    return flashcard


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
    db.delete(word)
    db.commit()
    return None


# ============================================================
# ALUNO: sessão de aprendizado (múltipla escolha, sempre 4 opções)
# ============================================================

def _require_student(user: User) -> None:
    if user.role != UserRole.aluno:
        raise HTTPException(status_code=403, detail="Apenas alunos podem usar o treino de vocabulário.")


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
    Monta a sessão de Aprender nesta ordem:
      1) até 15 palavras novas (nunca respondidas)
      2) palavras erradas anteriormente (sem primeiro acerto) — aparecem
         depois das novas; o frontend também pode recolocá-las ao fim da
         sessão atual quando o aluno erra de novo.

    Só entram palavras da língua-alvo do próprio aluno (`student_language`).
    Sem esse filtro, um aluno com palavras atribuídas em mais de uma língua
    (ex.: dados de teste com Inglês, Italiano, Francês etc.) via um único
    `student_id` acabava puxando a fila e as contagens de TODAS as línguas
    misturadas — inflando o total exibido bem além do que existe na
    categoria em questão.
    """
    _require_student(student)
    language = student_language(student)

    assigned_subquery = db.query(VocabWordAssignment.word_id).filter(
        VocabWordAssignment.student_id == student.id
    )
    attempted_subquery = db.query(VocabWordProgress.word_id).filter(
        VocabWordProgress.student_id == student.id
    )

    new_words = (
        db.query(VocabWord)
        .filter(VocabWord.id.in_(assigned_subquery))
        .filter(VocabWord.language == language)
        .filter(~VocabWord.id.in_(attempted_subquery))
        .order_by(VocabWord.created_at.asc())
        .limit(NEW_WORDS_PER_CYCLE)
        .all()
    )

    already_in_cycle_ids = [w.id for w in new_words]
    wrong_words = (
        db.query(VocabWord)
        .join(VocabWordProgress, VocabWordProgress.word_id == VocabWord.id)
        .filter(VocabWordProgress.student_id == student.id)
        .filter(VocabWordProgress.first_correct_at.is_(None))
        .filter(VocabWord.language == language)
        .filter(~VocabWord.id.in_(already_in_cycle_ids))
        .order_by(VocabWordProgress.last_reviewed.asc())
        .all()
    )

    cycle_words = new_words + wrong_words
    cards = [
        VocabLearnCardOut(
            word_id=w.id,
            word=w.word,
            part_of_speech=w.part_of_speech,
            example_sentence=w.example_sentence,
            tip=w.tip,
            options=_build_options(w),
        )
        for w in cycle_words
    ]

    total_assigned = (
        db.query(VocabWordAssignment)
        .join(VocabWord, VocabWord.id == VocabWordAssignment.word_id)
        .filter(
            VocabWordAssignment.student_id == student.id,
            VocabWord.language == language,
        )
        .count()
    )
    total_learned = (
        db.query(VocabWordProgress)
        .join(VocabWord, VocabWord.id == VocabWordProgress.word_id)
        .filter(
            VocabWordProgress.student_id == student.id,
            VocabWordProgress.first_correct_at.isnot(None),
            VocabWord.language == language,
        )
        .count()
    )

    return VocabLearnQueueOut(
        cards=cards,
        total_assigned=total_assigned,
        total_learned=total_learned,
        new_words_count=len(new_words),
    )


@router.post("/learn/{word_id}", response_model=VocabLearnResult)
def submit_learn_answer(
    word_id: int,
    payload: VocabLearnSubmit,
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """O aluno escolheu uma das 4 opções. No primeiro acerto, a palavra
    sai de Aprender e entra em Revisar como flashcard."""
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

    progress = (
        db.query(VocabWordProgress)
        .filter(VocabWordProgress.student_id == student.id, VocabWordProgress.word_id == word_id)
        .first()
    )
    if progress and progress.first_correct_at:
        raise HTTPException(
            status_code=409,
            detail="Esta palavra já foi aprendida e não está mais disponível em Aprender.",
        )

    is_correct = payload.selected_option.strip().lower() == word.translation.strip().lower()
    now = datetime.utcnow()

    if not progress:
        progress = VocabWordProgress(student_id=student.id, word_id=word_id)
        db.add(progress)

    progress.last_reviewed = now

    graduated = False
    if is_correct:
        progress.first_correct_at = now
        progress.status = VocabWordStatus.em_revisao
        _graduate_word_to_review(word, student, db)
        graduated = True
    else:
        progress.status = VocabWordStatus.nova

    db.commit()

    return VocabLearnResult(
        correct=is_correct,
        correct_answer=word.translation,
        explanation=word.explanation,
        graduated_to_review=graduated,
    )


@router.post("/learn/{word_id}/pronounce", response_model=FlashcardPronunciationResult)
async def pronounce_vocab_word(
    word_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    Prática opcional de pronúncia na tela Aprender.
    Não altera progresso nem acerto do card.
    """
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

    from app.routers.pronunciation import PronunciationAssessmentUnavailable, assess_pronunciation

    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Áudio muito curto ou inválido.")

    from app.pronunciation_limits import enforce_optional_pronunciation_limits, log_pronunciation_attempt

    enforce_optional_pronunciation_limits(db, student.id, audio_bytes)

    lang = student_language(student)
    speech_lang_map = {"ingles": "english", "italiano": "italian", "frances": "french"}
    speech_lang = speech_lang_map.get(lang, "english")
    expected = word.word

    try:
        assessment = assess_pronunciation(audio_bytes, speech_lang, expected)
    except PronunciationAssessmentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro na avaliação de pronúncia: {exc}") from exc

    score = assessment["score"]
    log_pronunciation_attempt(db, student.id)

    return FlashcardPronunciationResult(
        correct=score >= 60,
        correct_answer=expected,
        transcribed_text=assessment.get("transcribed_text") or None,
        feedback_title=assessment.get("feedback_title"),
        reason=assessment.get("feedback_detail"),
        score=score,
        word_scores=assessment.get("word_scores"),
    )


# ============================================================
# PROFESSOR: vocabulário (Aprender) de um aluno específico
# ============================================================

def _professor_status_label(progress: VocabWordProgress | None) -> VocabWordStatus:
    if not progress:
        return VocabWordStatus.nova
    if progress.first_correct_at:
        return VocabWordStatus.aprendida
    return VocabWordStatus.nova


@router.get("/vocabulary/{student_id}", response_model=list[VocabWordProgressOut])
def get_student_vocab_progress(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista as palavras atribuídas a um aluno, com o status atual."""
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
                status=_professor_status_label(progress),
                next_review=progress.next_review if progress else now,
            )
        )
    return items


def migrate_legacy_vocab_to_review(db: Session) -> None:
    """Migra dados antigos: palavras que já tinham progresso em Aprender
    passam a ter flashcard em Revisar e first_correct_at preenchido."""
    legacy_rows = (
        db.query(VocabWordProgress, VocabWord, User)
        .join(VocabWord, VocabWord.id == VocabWordProgress.word_id)
        .join(User, User.id == VocabWordProgress.student_id)
        .filter(
            VocabWordProgress.first_correct_at.is_(None),
            VocabWordProgress.status.in_([
                VocabWordStatus.em_revisao,
                VocabWordStatus.aprendida,
            ]),
        )
        .all()
    )
    if not legacy_rows:
        return

    for progress, word, student in legacy_rows:
        progress.first_correct_at = progress.last_reviewed or progress.next_review or datetime.utcnow()
        _graduate_word_to_review(word, student, db)

    db.commit()
