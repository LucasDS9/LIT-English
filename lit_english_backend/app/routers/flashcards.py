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
from app.models import CardProgress, Flashcard, FlashcardAssignment, QAAnswerLog, ReviewLog, User, UserRole
from app.schemas import (
    CardProgressOut,
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
