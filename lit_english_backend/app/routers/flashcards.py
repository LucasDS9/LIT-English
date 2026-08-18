"""
Rotas de Flashcards:
- Professor: criar, listar, editar e excluir flashcards
- Aluno: revisar flashcards (spaced repetition SM-2), respeitando limite por janela de tempo
"""
import logging
import random
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import case, nullsfirst
from sqlalchemy.orm import Session

from app.activity_queue import should_defer_flashcards
from app.ai_judge import judge_answer
from app.ai_translate import TranslationUnavailable, translate_flashcard_front
from app.flashcard_judge import judge_flashcard_answer
from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.lit_points import maybe_award_flashcard_daily_bonus
from app.language import student_language, student_source_language
from app.models import (
    CardProgress,
    Flashcard,
    FlashcardAssignment,
    FlashcardBatch,
    FlashcardBatchItem,
    FlashcardBatchStudent,
    FlashcardSource,
    StarterFlashcard,
    QAAnswerLog,
    ReviewCardStatus,
    ReviewMode,
    ReviewLog,
    User,
    UserRole,
)
from app.schemas import (
    CardProgressOut,
    FlashcardBatchCardOut,
    FlashcardBatchCreatePayload,
    FlashcardBatchOut,
    FlashcardBatchRenamePayload,
    FlashcardBatchResendPayload,
    FlashcardBatchStudentOut,
    FlashcardCreate,
    FlashcardOut,
    FlashcardPronunciationResult,
    FlashcardResendPayload,
    FlashcardSelfAdd,
    StarterCatalogCardOut,
    StarterCatalogUpsert,
    FlashcardStarterClaim,
    FlashcardUpdate,
    ReviewCardOut,
    ReviewQueueOut,
    ReviewResultOut,
    ReviewSubmit,
    VocabularyItemOut,
)
from app.routers.pronunciation import PronunciationAssessmentUnavailable, assess_pronunciation, transcribe
from app.sm2 import calculate_sm2

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])
logger = logging.getLogger(__name__)

# Limite de revisões por janela de tempo (igual ao seu app antigo: 15 cards a cada 12h)
LIMIT_PER_WINDOW = 15
WINDOW_HOURS = 12


def _normalize_answer(text: str) -> str:
    return (text or "").strip().lower()


_WHISPER_LANGUAGE = {
    "ingles": "english",
    "italiano": "italian",
    "frances": "french",
}

_ANSWER_LANGUAGE = {
    "italiano": "italiano",
    "frances": "francês",
    "ingles": "inglês",
}

_SPEAK_MODES = (ReviewMode.type_speak, ReviewMode.type_target)


def _judge_spoken_answer(*, student: User, expected: str, given: str, context: str) -> dict:
    """Julga pronúncia/transcrição na língua-alvo."""
    lang = student_language(student)
    if lang in ("italiano", "frances"):
        result = judge_flashcard_answer(
            expected=expected,
            given=given,
            target_language=lang,
            answer_language=_ANSWER_LANGUAGE[lang],
            context=context,
        )
        return {"correct": result["correct"], "reason": result["reason"], "confidence": result.get("confidence")}
    result = judge_answer(expected=expected, given=given, context=context)
    return {"correct": result["correct"], "reason": result["reason"], "confidence": None}


def _check_typed_answer(
    *,
    expected: str,
    given: str,
    student: User,
    flashcard: Flashcard,
) -> dict:
    """
    Verifica resposta digitada em português.
    Todos os idiomas-alvo usam comparação semântica com IA, para aceitar
    traduções naturais equivalentes (não apenas a tradução cadastrada).
    """
    lang = student_language(student)
    return judge_flashcard_answer(
        expected=expected,
        given=given,
        target_language=lang,
        answer_language="português",
        context=flashcard.front,
    )


def _require_assigned_flashcard(flashcard_id: int, student_id: int, db: Session) -> Flashcard:
    flashcard = db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
    if not flashcard:
        raise HTTPException(status_code=404, detail="Flashcard não encontrado.")
    assigned = (
        db.query(FlashcardAssignment)
        .filter(
            FlashcardAssignment.flashcard_id == flashcard_id,
            FlashcardAssignment.student_id == student_id,
        )
        .first()
    )
    if not assigned:
        raise HTTPException(status_code=404, detail="Flashcard não encontrado.")
    return flashcard


def _apply_sm2(progress: CardProgress, quality: int) -> None:
    result = calculate_sm2(
        quality=quality,
        repetitions=progress.repetitions,
        interval_days=progress.interval_days,
        ease_factor=progress.ease_factor,
    )
    progress.repetitions = result.repetitions
    progress.interval_days = result.interval_days
    progress.ease_factor = result.ease_factor
    progress.next_review = result.next_review
    progress.last_reviewed = datetime.utcnow()


def _card_mode(progress: CardProgress | None) -> ReviewMode:
    if progress and progress.review_mode:
        return progress.review_mode
    return ReviewMode.flip


def _card_status(progress: CardProgress | None) -> ReviewCardStatus | None:
    return progress.review_status if progress else None


# ============================================================
# PROFESSOR: CRUD de flashcards
# ============================================================

def _validate_student_ids(student_ids: list[int], db: Session) -> None:
    found = (
        db.query(User.id)
        .filter(User.id.in_(student_ids), User.role == UserRole.aluno)
        .count()
    )
    if found != len(set(student_ids)):
        raise HTTPException(status_code=404, detail="Um ou mais alunos selecionados não foram encontrados.")


@router.post("", response_model=FlashcardOut, status_code=status.HTTP_201_CREATED)
def create_flashcard(
    data: FlashcardCreate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    _validate_student_ids(data.student_ids, db)

    card = Flashcard(front=data.front, back=data.back, description=(data.description or "").strip() or None, source=FlashcardSource.professor)
    db.add(card)
    db.flush()

    for student_id in set(data.student_ids):
        db.add(FlashcardAssignment(flashcard_id=card.id, student_id=student_id))

    db.commit()
    db.refresh(card)
    return card


@router.get("", response_model=list[FlashcardOut])
def list_flashcards(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista todos os flashcards cadastrados (visão do professor)."""
    return db.query(Flashcard).order_by(Flashcard.created_at.desc()).all()


@router.put("/{flashcard_id}", response_model=FlashcardOut)
def update_flashcard(
    flashcard_id: int,
    data: FlashcardUpdate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    card = db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard não encontrado.")

    if data.front is not None:
        card.front = data.front
    if data.back is not None:
        card.back = data.back
    if data.description is not None:
        card.description = data.description.strip() or None

    if data.student_ids is not None:
        if len(data.student_ids) == 0:
            raise HTTPException(status_code=400, detail="Selecione ao menos um aluno.")
        _validate_student_ids(data.student_ids, db)
        db.query(FlashcardAssignment).filter(FlashcardAssignment.flashcard_id == card.id).delete()
        for student_id in set(data.student_ids):
            db.add(FlashcardAssignment(flashcard_id=card.id, student_id=student_id))

    db.commit()
    db.refresh(card)
    return card


@router.delete("/{flashcard_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flashcard(
    flashcard_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    card = db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard não encontrado.")

    # Remove o progresso de revisão (SM-2) e o histórico de revisões deste
    # card. As atribuições (FlashcardAssignment) já são removidas pelo
    # cascade da relationship "assignments" do model Flashcard.
    db.query(CardProgress).filter(CardProgress.flashcard_id == flashcard_id).delete()
    db.query(ReviewLog).filter(ReviewLog.flashcard_id == flashcard_id).delete()
    db.query(FlashcardBatchItem).filter(FlashcardBatchItem.flashcard_id == flashcard_id).delete()
    # QAAnswerLog mantém o histórico de respostas do QA mesmo se o flashcard
    # gerado a partir dela for excluído — só desvincula.
    db.query(QAAnswerLog).filter(QAAnswerLog.flashcard_id == flashcard_id).update(
        {QAAnswerLog.flashcard_id: None}
    )

    db.delete(card)
    db.commit()
    return None


@router.post("/resend", status_code=200)
def resend_flashcards(
    payload: FlashcardResendPayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Reenvia (atribui) um ou mais flashcards já existentes a outro(s) aluno(s),
    sem afetar quem já os recebeu. Usado pelo botão "Selecionar" no
    Vocabulário do aluno.
    """
    cards = db.query(Flashcard).filter(Flashcard.id.in_(payload.flashcard_ids)).all()
    found_card_ids = {c.id for c in cards}
    missing_cards = set(payload.flashcard_ids) - found_card_ids
    if missing_cards:
        raise HTTPException(status_code=404, detail=f"Flashcard(s) não encontrado(s): {list(missing_cards)}")

    _validate_student_ids(payload.student_ids, db)

    # Assignments já existentes, pra não duplicar (violaria a constraint única).
    existing = (
        db.query(FlashcardAssignment.flashcard_id, FlashcardAssignment.student_id)
        .filter(
            FlashcardAssignment.flashcard_id.in_(payload.flashcard_ids),
            FlashcardAssignment.student_id.in_(payload.student_ids),
        )
        .all()
    )
    existing_pairs = {(fid, sid) for fid, sid in existing}

    total = 0
    for flashcard_id in payload.flashcard_ids:
        for student_id in set(payload.student_ids):
            if (flashcard_id, student_id) in existing_pairs:
                continue
            db.add(FlashcardAssignment(flashcard_id=flashcard_id, student_id=student_id))
            total += 1

    db.commit()
    return {"assigned": total}


@router.post("/batch", response_model=FlashcardBatchOut, status_code=status.HTTP_201_CREATED)
def create_flashcard_batch(
    payload: FlashcardBatchCreatePayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Cria vários flashcards de uma vez (um "deck"), já atribuídos aos alunos
    selecionados, e agrupa tudo num lote que aparece no Histórico — mesmo
    padrão usado no envio de exercícios em lote.
    """
    _validate_student_ids(payload.student_ids, db)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Informe um nome para o deck.")

    now = datetime.utcnow()
    batch = FlashcardBatch(name=name, sent_at=now)
    db.add(batch)
    db.flush()  # gera batch.id

    student_ids = set(payload.student_ids)
    created_cards = []
    for card_in in payload.cards:
        card = Flashcard(
            front=card_in.front.strip(),
            back=card_in.back.strip(),
            source=FlashcardSource.professor,
        )
        db.add(card)
        db.flush()  # gera card.id
        db.add(FlashcardBatchItem(batch_id=batch.id, flashcard_id=card.id))
        for student_id in student_ids:
            db.add(FlashcardAssignment(flashcard_id=card.id, student_id=student_id))
        created_cards.append(card)

    for student_id in student_ids:
        db.add(FlashcardBatchStudent(batch_id=batch.id, student_id=student_id))

    db.commit()

    students = db.query(User).filter(User.id.in_(student_ids)).all()
    return FlashcardBatchOut(
        batch_id=batch.id,
        batch_name=batch.name,
        sent_at=batch.sent_at,
        students=[FlashcardBatchStudentOut(id=s.id, name=s.name) for s in students],
        cards=[FlashcardBatchCardOut(id=c.id, front=c.front, back=c.back) for c in created_cards],
    )


# ============================================================
# PROFESSOR: histórico de lotes (decks) de flashcards
# ============================================================

@router.get("/batches", response_model=list[FlashcardBatchOut])
def list_flashcard_batches(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista todos os decks de flashcards enviados, do mais recente para o mais antigo."""
    batches = db.query(FlashcardBatch).order_by(FlashcardBatch.sent_at.desc()).all()

    result = []
    for batch in batches:
        cards = [item.flashcard for item in batch.items if item.flashcard]
        students = [link.student for link in batch.student_links if link.student]
        result.append(
            FlashcardBatchOut(
                batch_id=batch.id,
                batch_name=batch.name,
                sent_at=batch.sent_at,
                students=[FlashcardBatchStudentOut(id=s.id, name=s.name) for s in students],
                cards=[FlashcardBatchCardOut(id=c.id, front=c.front, back=c.back) for c in cards],
            )
        )
    return result


@router.patch("/batches/{batch_id}/rename", status_code=200)
def rename_flashcard_batch(
    batch_id: int,
    payload: FlashcardBatchRenamePayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    batch = db.query(FlashcardBatch).filter(FlashcardBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Deck não encontrado.")
    new_name = payload.name.strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="Informe um nome.")
    batch.name = new_name
    db.commit()
    return {"ok": True}


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flashcard_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Remove um deck do histórico. Isso NÃO revoga os flashcards já atribuídos
    aos alunos (eles continuam disponíveis para revisão); apenas o registro
    do histórico (e seus vínculos de card/aluno) é excluído.
    """
    batch = db.query(FlashcardBatch).filter(FlashcardBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Deck não encontrado.")
    db.delete(batch)
    db.commit()
    return None


@router.post("/batches/{batch_id}/resend", status_code=201)
def resend_flashcard_batch(
    batch_id: int,
    payload: FlashcardBatchResendPayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Reenvia todos os flashcards de um deck para os alunos informados.
    Cria um novo lote no histórico com o mesmo nome do original.
    """
    original = db.query(FlashcardBatch).filter(FlashcardBatch.id == batch_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Deck não encontrado.")

    card_ids = [item.flashcard_id for item in original.items]
    if not card_ids:
        raise HTTPException(status_code=422, detail="Deck sem flashcards.")

    students = (
        db.query(User)
        .filter(User.id.in_(payload.student_ids), User.role == UserRole.aluno)
        .all()
    )
    if not students:
        raise HTTPException(status_code=404, detail="Nenhum aluno válido informado.")

    existing = (
        db.query(FlashcardAssignment.flashcard_id, FlashcardAssignment.student_id)
        .filter(
            FlashcardAssignment.flashcard_id.in_(card_ids),
            FlashcardAssignment.student_id.in_([s.id for s in students]),
        )
        .all()
    )
    existing_pairs = {(fid, sid) for fid, sid in existing}

    now = datetime.utcnow()
    new_batch = FlashcardBatch(name=original.name, sent_at=now)
    db.add(new_batch)
    db.flush()

    for card_id in card_ids:
        db.add(FlashcardBatchItem(batch_id=new_batch.id, flashcard_id=card_id))

    total = 0
    for student in students:
        db.add(FlashcardBatchStudent(batch_id=new_batch.id, student_id=student.id))
        for card_id in card_ids:
            if (card_id, student.id) in existing_pairs:
                continue
            db.add(FlashcardAssignment(flashcard_id=card_id, student_id=student.id))
            total += 1

    db.commit()
    return {"assigned": total}


# ============================================================
# CATÁLOGO: flashcards sugeridos no primeiro acesso
# ============================================================

_PLACEHOLDER_RE = re.compile(r"<([^<>]+)>")


def _extract_placeholders(*texts: str) -> list[str]:
    found = []
    seen = set()
    for text in texts:
        for match in _PLACEHOLDER_RE.findall(text or ""):
            value = match.strip()
            if value and value.lower() not in seen:
                seen.add(value.lower())
                found.append(value)
    return found


@router.get("/starter/catalog", response_model=list[StarterCatalogCardOut])
def get_starter_catalog(
    language: str = "ingles",
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """Retorna os exemplos ativos da língua-alvo do aluno.

    Tokens entre < > são identificados no backend e devolvidos em
    `placeholders`, mas o texto original é preservado exatamente como foi
    enviado pelo professor.
    """
    if student.role != UserRole.aluno:
        raise HTTPException(status_code=403, detail="Apenas alunos podem consultar o catálogo inicial.")

    requested = (language or "ingles").strip().lower()
    actual = student_language(student).strip().lower()
    if requested != actual:
        requested = actual
    source = student_source_language(student)

    cards = (
        db.query(StarterFlashcard)
        .filter(
            StarterFlashcard.source_language == source,
            StarterFlashcard.language == requested,
            StarterFlashcard.active.is_(True),
        )
        .order_by(StarterFlashcard.id.asc())
        .all()
    )
    return [
        StarterCatalogCardOut(
            id=card.id,
            source_language=card.source_language,
            language=card.language,
            front=card.front,
            back=card.back,
            description=card.description,
            placeholders=card.placeholders or _extract_placeholders(card.front, card.back, card.description or ""),
            category=card.category,
        )
        for card in cards
    ]


@router.post("/starter/catalog", status_code=status.HTTP_200_OK)
def upsert_starter_catalog(
    data: StarterCatalogUpsert,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Cria/atualiza o pacote de exemplos usado no primeiro acesso.

    O professor pode enviar novamente a lista pelo script de seed sem criar
    duplicatas. Placeholders como <name>, <age> e <language> são detectados
    automaticamente e armazenados separadamente, enquanto o texto original
    continua intacto para aparecer no flashcard.
    """
    source_language = (data.source_language or "pt").strip().lower()
    language = (data.language or "ingles").strip().lower()
    if not source_language or not language:
        raise HTTPException(status_code=400, detail="source_language e language são obrigatórios.")
    created = updated = unchanged = 0
    incoming_keys = set()

    for item in data.cards:
        front = item.front.strip()
        back = item.back.strip()
        if not front or not back:
            continue
        description = (item.description or "").strip() or None
        category = (item.category or "saudacoes").strip().lower() or "saudacoes"
        placeholders = _extract_placeholders(front, back, description or "")
        key = (front.casefold(), back.casefold())
        incoming_keys.add(key)

        card = (
            db.query(StarterFlashcard)
            .filter(
                StarterFlashcard.source_language == source_language,
                StarterFlashcard.language == language,
                StarterFlashcard.front == front,
                StarterFlashcard.back == back,
            )
            .first()
        )
        if card is None:
            db.add(StarterFlashcard(
                source_language=source_language,
                language=language,
                front=front,
                back=back,
                description=description,
                placeholders=placeholders,
                category=category,
                active=True,
            ))
            created += 1
            continue

        changed = (
            card.description != description
            or (card.placeholders or []) != placeholders
            or card.category != category
            or not card.active
        )
        if changed:
            card.description = description
            card.placeholders = placeholders
            card.category = category
            card.active = True
            updated += 1
        else:
            unchanged += 1

    # O seed representa o catálogo completo: itens antigos que não estão mais
    # na lista deixam de aparecer para novos alunos, mas não são apagados.
    existing_cards = db.query(StarterFlashcard).filter(
        StarterFlashcard.source_language == source_language,
        StarterFlashcard.language == language,
    ).all()
    for card in existing_cards:
        if (card.front.casefold(), card.back.casefold()) not in incoming_keys:
            card.active = False

    db.commit()
    return {"source_language": source_language, "language": language, "created": created, "updated": updated, "unchanged": unchanged, "total": len(incoming_keys)}


# ============================================================
# ALUNO: receber pacote inicial de flashcards
# ============================================================

@router.post("/starter/claim", status_code=status.HTTP_201_CREATED)
def claim_starter_flashcards(
    data: FlashcardStarterClaim,
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """Cria e atribui ao aluno os cards do pacote inicial.

    A operação é idempotente por conteúdo: se o mesmo card já estiver
    atribuído ao aluno, ele não é duplicado.
    """
    if student.role != UserRole.aluno:
        raise HTTPException(status_code=403, detail="Apenas alunos podem receber flashcards.")

    created = []
    skipped = 0

    for item in data.cards:
        front = (item.front or "").strip()
        back = (item.back or "").strip()
        description = (item.description or "").strip() or None
        if not front or not back:
            continue

        existing = (
            db.query(Flashcard)
            .join(FlashcardAssignment, FlashcardAssignment.flashcard_id == Flashcard.id)
            .filter(
                FlashcardAssignment.student_id == student.id,
                Flashcard.front == front,
                Flashcard.back == back,
            )
            .first()
        )
        if existing:
            skipped += 1
            continue

        card = Flashcard(
            front=front,
            back=back,
            description=description,
            source=FlashcardSource.aluno,
        )
        db.add(card)
        db.flush()
        db.add(FlashcardAssignment(flashcard_id=card.id, student_id=student.id))
        created.append(card.id)

    db.commit()
    return {"received": len(created), "skipped": skipped, "flashcard_ids": created}


# ============================================================
# ALUNO: salvar frase do popup de vocabulário direto como flashcard
# ============================================================

@router.post("/self-add", response_model=FlashcardOut, status_code=status.HTTP_201_CREATED)
def self_add_flashcard(
    data: FlashcardSelfAdd,
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    Aluno cria um flashcard próprio, sem depender do professor — seja
    clicando em "Salvar frase nos flashcards" no popup de vocabulário (Read
    and Listen, front+back sempre vêm preenchidos), seja pelo botão
    "Adicionar flashcard" da tela de Flashcards (frente na língua-alvo do
    aluno; verso opcional — se vier vazio, geramos a tradução
    automaticamente pra português, na língua-alvo certa: inglês pro curso
    normal, ou a língua do Acesso Especial, ex.: italiano).
    Card já sai atribuído a ele mesmo, pra aparecer na fila de revisão
    (SM-2) igual a qualquer outro flashcard.
    """
    if student.role != UserRole.aluno:
        raise HTTPException(status_code=403, detail="Apenas alunos podem salvar flashcards por conta própria.")

    front = data.front.strip()
    if not front:
        raise HTTPException(status_code=422, detail="Escreva o termo ou frase na língua-alvo.")

    back = (data.back or "").strip()
    if not back:
        try:
            native_language = student.native_language or "pt"
            back = translate_flashcard_front(
                front,
                native_language=native_language,
                target_language=student_language(student),
            )
        except (TranslationUnavailable, ValueError):
            raise HTTPException(
                status_code=502,
                detail="Não foi possível gerar a tradução automaticamente agora. Preencha o verso e tente de novo.",
            )

    card = Flashcard(
        front=front,
        back=back,
        description=(data.description or "").strip() or None,
        source=FlashcardSource.aluno,
    )
    db.add(card)
    db.flush()
    db.add(FlashcardAssignment(flashcard_id=card.id, student_id=student.id))
    db.commit()
    db.refresh(card)
    return card


# ============================================================
# ALUNO: revisão com SM-2
# ============================================================

def _remaining_in_window(student_id: int, db: Session) -> int:
    """Quantas revisões o aluno ainda pode fazer na janela de tempo atual."""
    window_start = datetime.utcnow() - timedelta(hours=WINDOW_HOURS)
    used = (
        db.query(ReviewLog)
        .filter(ReviewLog.student_id == student_id, ReviewLog.reviewed_at >= window_start)
        .count()
    )
    return max(0, LIMIT_PER_WINDOW - used)


def _require_student(user: User) -> None:
    if user.role != UserRole.aluno:
        raise HTTPException(status_code=403, detail="Apenas alunos podem revisar flashcards.")


@router.get("/review/next", response_model=ReviewQueueOut)
def get_review_queue(
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    Retorna os próximos flashcards que o aluno precisa revisar agora,
    respeitando o limite de cards por janela de tempo.
    """
    _require_student(student)

    if should_defer_flashcards(db, student):
        return ReviewQueueOut(
            cards=[],
            remaining_in_window=0,
            limit_per_window=LIMIT_PER_WINDOW,
            blocked_by="exercises",
            blocked_message=(
                "Complete os exercícios atribuídos pelo professor antes de revisar flashcards."
            ),
        )

    remaining = _remaining_in_window(student.id, db)

    if remaining == 0:
        return ReviewQueueOut(cards=[], remaining_in_window=0, limit_per_window=LIMIT_PER_WINDOW)


    now = datetime.utcnow()

    # IDs de cards atribuídos a este aluno
    assigned_subquery = db.query(FlashcardAssignment.flashcard_id).filter(
        FlashcardAssignment.student_id == student.id
    )

    # IDs de cards que ainda NÃO estão prontos para revisão (next_review no
    # futuro).
    not_due_subquery = db.query(CardProgress.flashcard_id).filter(
        CardProgress.student_id == student.id,
        CardProgress.next_review > now,
    )

    # Flashcards do professor entram primeiro na fila — dentro de cada grupo
    # (professor / aluno), a ordem continua sendo por vencimento (SM-2).
    source_priority = case((Flashcard.source == FlashcardSource.professor, 0), else_=1)

    due_cards = (
        db.query(Flashcard, CardProgress)
        .outerjoin(
            CardProgress,
            (CardProgress.flashcard_id == Flashcard.id) & (CardProgress.student_id == student.id),
        )
        .filter(Flashcard.id.in_(assigned_subquery))
        .filter(~Flashcard.id.in_(not_due_subquery))
        .order_by(
            source_priority,
            nullsfirst(CardProgress.next_review),
        )
        .limit(remaining)
        .all()
    )


    cards_out = [
        ReviewCardOut(
            flashcard_id=card.id,
            front=card.front,
            back=card.back,
            description=card.description,
            status=_card_status(progress),
            mode=_card_mode(progress),
        )
        for card, progress in due_cards
    ]
    return ReviewQueueOut(
        cards=cards_out,
        remaining_in_window=remaining,
        limit_per_window=LIMIT_PER_WINDOW,
    )


@router.post("/review/{flashcard_id}", response_model=ReviewResultOut)
def submit_review(
    flashcard_id: int,
    payload: ReviewSubmit,
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    Submissão de revisão — flip (Esqueci…Fácil) ou digitação (Dominando).
    Cada etapa agenda a próxima via SM-2 (next_review).
    """
    _require_student(student)

    remaining = _remaining_in_window(student.id, db)
    if remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite de {LIMIT_PER_WINDOW} cards a cada {WINDOW_HOURS}h atingido. Volte mais tarde.",
        )

    flashcard = db.query(Flashcard).filter(Flashcard.id == flashcard_id).first()
    if not flashcard:
        raise HTTPException(status_code=404, detail="Flashcard não encontrado.")

    progress = (
        db.query(CardProgress)
        .filter(CardProgress.student_id == student.id, CardProgress.flashcard_id == flashcard_id)
        .first()
    )
    if not progress:
        progress = CardProgress(
            student_id=student.id,
            flashcard_id=flashcard_id,
            review_status=ReviewCardStatus.concluido,
            review_mode=ReviewMode.flip,
        )
        db.add(progress)
        db.flush()

    mode = progress.review_mode or ReviewMode.flip

    # ── Digitação em português (Dominando — type_pt) ─────────────────────
    if mode == ReviewMode.type_pt:
        if not payload.typed_answer or not payload.typed_answer.strip():
            raise HTTPException(status_code=422, detail="Digite sua resposta.")

        expected = flashcard.back
        judge_result = _check_typed_answer(
            expected=expected,
            given=payload.typed_answer,
            student=student,
            flashcard=flashcard,
        )
        is_correct = judge_result["correct"]
        quality = 5 if is_correct else 0

        _apply_sm2(progress, quality)

        if is_correct:
            progress.review_mode = ReviewMode.type_speak

        db.add(ReviewLog(student_id=student.id, flashcard_id=flashcard_id))
        db.flush()
        maybe_award_flashcard_daily_bonus(db, student.id)
        db.commit()

        return ReviewResultOut(
            correct=is_correct,
            correct_answer=expected,
            review_status=progress.review_status,
            review_mode=progress.review_mode,
            reason=judge_result.get("reason"),
            confidence=judge_result.get("confidence"),
        )

    if mode in _SPEAK_MODES:
        raise HTTPException(
            status_code=422,
            detail="Use o envio de áudio para este exercício de pronúncia.",
        )

    # ── Flip (Aprendendo / Concluído) ─────────────────────────────────────
    if payload.quality is None:
        raise HTTPException(status_code=422, detail="Informe a avaliação (quality).")

    quality = payload.quality
    _apply_sm2(progress, quality)

    if progress.review_status is None:
        progress.review_status = ReviewCardStatus.concluido

    # Aprendendo + Fácil (1x) → Dominando (primeiro: digitar em português).
    if progress.review_status == ReviewCardStatus.aprendendo and quality == 5:
        progress.review_status = ReviewCardStatus.dominando
        progress.review_mode = ReviewMode.type_pt

    db.add(ReviewLog(student_id=student.id, flashcard_id=flashcard_id))
    db.flush()
    maybe_award_flashcard_daily_bonus(db, student.id)
    db.commit()

    return ReviewResultOut(
        correct=quality >= 3,
        review_status=progress.review_status,
        review_mode=progress.review_mode,
    )


@router.post("/review/{flashcard_id}/pronounce", response_model=FlashcardPronunciationResult)
async def pronounce_flashcard(
    flashcard_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    Prática opcional de pronúncia em flashcards.
    Não altera SM-2, não consome limite de revisão, não bloqueia avanço.
    """
    _require_student(student)
    flashcard = _require_assigned_flashcard(flashcard_id, student.id, db)

    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Áudio muito curto ou inválido.")

    from app.pronunciation_limits import enforce_optional_pronunciation_limits, log_pronunciation_attempt

    enforce_optional_pronunciation_limits(db, student.id, audio_bytes)

    lang = student_language(student)
    speech_lang = _WHISPER_LANGUAGE.get(lang, "english")
    expected = flashcard.front

    try:
        assessment = assess_pronunciation(audio_bytes, speech_lang, expected)
    except PronunciationAssessmentUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Erro na avaliação de pronúncia de flashcard")
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


@router.post("/review/{flashcard_id}/submit-speak", response_model=ReviewResultOut)
async def submit_speak_review(
    flashcard_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    Exercício obrigatório de pronúncia (Dominando — type_speak):
    frase em português, aluno fala na língua-alvo. Atualiza SM-2.
    """
    _require_student(student)

    remaining = _remaining_in_window(student.id, db)
    if remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite de {LIMIT_PER_WINDOW} cards a cada {WINDOW_HOURS}h atingido. Volte mais tarde.",
        )

    flashcard = _require_assigned_flashcard(flashcard_id, student.id, db)

    progress = (
        db.query(CardProgress)
        .filter(CardProgress.student_id == student.id, CardProgress.flashcard_id == flashcard_id)
        .first()
    )
    if not progress:
        raise HTTPException(status_code=422, detail="Este card ainda não está em modo de pronúncia.")

    mode = progress.review_mode or ReviewMode.flip
    if mode not in _SPEAK_MODES:
        raise HTTPException(status_code=422, detail="Este card não está no exercício de pronúncia.")

    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Áudio muito curto ou inválido.")

    lang = student_language(student)
    whisper_lang = _WHISPER_LANGUAGE.get(lang, "english")

    try:
        transcribed_text = transcribe(audio_bytes, whisper_lang)
    except Exception as exc:
        logger.exception("Erro na transcrição do exercício de pronúncia")
        raise HTTPException(status_code=500, detail=f"Erro na transcrição: {exc}")

    transcribed_text = transcribed_text or ""
    expected = flashcard.front
    judge_result = _judge_spoken_answer(
        student=student,
        expected=expected,
        given=transcribed_text,
        context=flashcard.back,
    )
    is_correct = judge_result["correct"]
    quality = 5 if is_correct else 0

    # Analisador visual de pronúncia: melhor
    # esforço — se a Azure não estiver configurada/disponível, seguimos só
    # com a correção semântica de sempre (transcrição + IA), sem quebrar o
    # exercício obrigatório de falar.
    score = None
    word_scores = None
    feedback_title = None
    try:
        assessment = assess_pronunciation(audio_bytes, whisper_lang, expected)
        score = assessment.get("score")
        word_scores = assessment.get("word_scores")
        feedback_title = assessment.get("feedback_title")
    except PronunciationAssessmentUnavailable:
        pass
    except Exception:
        logger.exception("Falha ao gerar análise visual de pronúncia (submit-speak) — ignorando.")

    _apply_sm2(progress, quality)
    if is_correct:
        progress.review_status = ReviewCardStatus.concluido
        progress.review_mode = ReviewMode.flip

    db.add(ReviewLog(student_id=student.id, flashcard_id=flashcard_id))
    db.flush()
    maybe_award_flashcard_daily_bonus(db, student.id)
    db.commit()

    return ReviewResultOut(
        correct=is_correct,
        correct_answer=expected,
        review_status=progress.review_status,
        review_mode=progress.review_mode,
        reason=judge_result.get("reason"),
        confidence=judge_result.get("confidence"),
        transcribed_text=transcribed_text or None,
        score=score,
        word_scores=word_scores,
        feedback_title=feedback_title,
    )


# ============================================================
# PROFESSOR: vocabulário de um aluno específico (status de revisão)
# ============================================================

@router.get("/vocabulary/{student_id}", response_model=list[VocabularyItemOut])
def get_student_vocabulary(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista os flashcards atribuídos a um aluno, com o status de revisão (SM-2)."""
    student = db.query(User).filter(User.id == student_id, User.role == UserRole.aluno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")

    now = datetime.utcnow()

    rows = (
        db.query(Flashcard, CardProgress)
        .join(FlashcardAssignment, FlashcardAssignment.flashcard_id == Flashcard.id)
        .outerjoin(
            CardProgress,
            (CardProgress.flashcard_id == Flashcard.id) & (CardProgress.student_id == student_id),
        )
        .filter(FlashcardAssignment.student_id == student_id)
        .order_by(Flashcard.created_at.desc())
        .all()
    )

    items = []
    for card, progress in rows:
        next_review = progress.next_review if progress else None
        is_due = next_review is None or next_review <= now
        items.append(
            VocabularyItemOut(
                flashcard_id=card.id,
                front=card.front,
                back=card.back,
                next_review=next_review,
                is_due=is_due,
                review_status=progress.review_status if progress else None,
                review_mode=progress.review_mode if progress else None,
            )
        )
    return items
