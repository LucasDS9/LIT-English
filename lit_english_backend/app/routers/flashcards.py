"""
Rotas de Flashcards:
- Professor: criar, listar, editar e excluir flashcards
- Aluno: revisar flashcards (spaced repetition SM-2), respeitando limite por janela de tempo
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import nullsfirst
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.lit_points import maybe_award_flashcard_daily_bonus
from app.models import (
    CardProgress,
    Flashcard,
    FlashcardAssignment,
    FlashcardBatch,
    FlashcardBatchItem,
    FlashcardBatchStudent,
    QAAnswerLog,
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
    FlashcardResendPayload,
    FlashcardUpdate,
    ReviewCardOut,
    ReviewQueueOut,
    ReviewSubmit,
    VocabularyItemOut,
)
from app.sm2 import calculate_sm2

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])

# Limite de revisões por janela de tempo (igual ao seu app antigo: 15 cards a cada 12h)
LIMIT_PER_WINDOW = 15
WINDOW_HOURS = 12


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

    card = Flashcard(front=data.front, back=data.back)
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
        card = Flashcard(front=card_in.front.strip(), back=card_in.back.strip())
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
    remaining = _remaining_in_window(student.id, db)

    if remaining == 0:
        return ReviewQueueOut(cards=[], remaining_in_window=0, limit_per_window=LIMIT_PER_WINDOW)

    now = datetime.utcnow()

    # IDs de cards atribuídos a este aluno
    assigned_subquery = db.query(FlashcardAssignment.flashcard_id).filter(
        FlashcardAssignment.student_id == student.id
    )

    # IDs de cards que ainda NÃO estão prontos para revisão (next_review no futuro)
    not_due_subquery = db.query(CardProgress.flashcard_id).filter(
        CardProgress.student_id == student.id,
        CardProgress.next_review > now,
    )

    due_cards = (
        db.query(Flashcard)
        .outerjoin(
            CardProgress,
            (CardProgress.flashcard_id == Flashcard.id) & (CardProgress.student_id == student.id),
        )
        .filter(Flashcard.id.in_(assigned_subquery))
        .filter(~Flashcard.id.in_(not_due_subquery))
        .order_by(nullsfirst(CardProgress.next_review))
        .limit(remaining)
        .all()
    )

    cards_out = [ReviewCardOut(flashcard_id=c.id, front=c.front, back=c.back) for c in due_cards]
    return ReviewQueueOut(
        cards=cards_out, remaining_in_window=remaining, limit_per_window=LIMIT_PER_WINDOW
    )


@router.post("/review/{flashcard_id}", response_model=CardProgressOut)
def submit_review(
    flashcard_id: int,
    payload: ReviewSubmit,
    db: Session = Depends(get_db),
    student: User = Depends(get_current_approved_user),
):
    """
    O aluno envia sua avaliação (0=errou, 3=difícil, 4=bom, 5=fácil) para um card.
    Atualiza o estado do SM-2 e registra a revisão (pra contar no limite da janela).
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
        progress = CardProgress(student_id=student.id, flashcard_id=flashcard_id)
        db.add(progress)
        db.flush()

    result = calculate_sm2(
        quality=payload.quality,
        repetitions=progress.repetitions,
        interval_days=progress.interval_days,
        ease_factor=progress.ease_factor,
    )
    progress.repetitions = result.repetitions
    progress.interval_days = result.interval_days
    progress.ease_factor = result.ease_factor
    progress.next_review = result.next_review
    progress.last_reviewed = datetime.utcnow()

    db.add(ReviewLog(student_id=student.id, flashcard_id=flashcard_id))
    db.flush()
    maybe_award_flashcard_daily_bonus(db, student.id)
    db.commit()
    db.refresh(progress)
    return progress


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
            )
        )
    return items
