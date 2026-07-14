"""
Rotas administrativas, acessíveis apenas pelo professor:
- listar alunos
- aprovar acesso de um aluno
- revogar/bloquear acesso de um aluno
- excluir aluno
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_professor
from app.database import get_db
from app.models import (
    CardProgress,
    ExerciseAssignment,
    ExerciseBatchStudent,
    ExerciseProgress,
    ExerciseSubmission,
    FlashcardAssignment,
    LitPointLog,
    QAAnswerLog,
    ReadingTimeLog,
    ReviewLog,
    TextAssignment,
    User,
    UserRole,
)
from app.routers.dashboard import build_dashboard_metrics
from app.schemas import StudentDetailsOut, UserOut

router = APIRouter(prefix="/admin", tags=["Admin (Professor)"])


def _get_student_or_404(student_id: int, db: Session) -> User:
    student = (
        db.query(User)
        .filter(User.id == student_id, User.role == UserRole.aluno)
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")
    return student


@router.get("/students", response_model=list[UserOut])
def list_students(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista todos os alunos cadastrados (aprovados e pendentes)."""
    return db.query(User).filter(User.role == UserRole.aluno).order_by(User.created_at.desc()).all()


@router.get("/students/{student_id}/details", response_model=StudentDetailsOut)
def get_student_details(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Detalhes de um aluno: quantidade de exercícios respondidos, tempo de
    texto e demais métricas (mesmas exibidas na tela inicial do aluno)."""
    student = _get_student_or_404(student_id, db)
    metrics = build_dashboard_metrics(db, student_id)
    return StudentDetailsOut(student=student, metrics=metrics)


@router.patch("/students/{student_id}/approve", response_model=UserOut)
def approve_student(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Aprova o acesso de um aluno."""
    student = _get_student_or_404(student_id, db)
    student.is_approved = True
    db.commit()
    db.refresh(student)
    return student


@router.patch("/students/{student_id}/revoke", response_model=UserOut)
def revoke_student(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Revoga/bloqueia o acesso de um aluno (ex: aluno parou as aulas)."""
    student = _get_student_or_404(student_id, db)
    student.is_approved = False
    db.commit()
    db.refresh(student)
    return student


@router.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Remove permanentemente um aluno e todos os dados associados."""
    student = _get_student_or_404(student_id, db)

    db.query(ExerciseSubmission).filter(ExerciseSubmission.student_id == student_id).delete()
    db.query(ExerciseAssignment).filter(ExerciseAssignment.student_id == student_id).delete()
    db.query(ExerciseProgress).filter(ExerciseProgress.student_id == student_id).delete()
    db.query(ExerciseBatchStudent).filter(ExerciseBatchStudent.student_id == student_id).delete()
    db.query(ReviewLog).filter(ReviewLog.student_id == student_id).delete()
    db.query(CardProgress).filter(CardProgress.student_id == student_id).delete()
    db.query(FlashcardAssignment).filter(FlashcardAssignment.student_id == student_id).delete()
    db.query(TextAssignment).filter(TextAssignment.student_id == student_id).delete()
    db.query(QAAnswerLog).filter(QAAnswerLog.student_id == student_id).delete()
    db.query(LitPointLog).filter(LitPointLog.student_id == student_id).delete()
    db.query(ReadingTimeLog).filter(ReadingTimeLog.student_id == student_id).delete()

    db.delete(student)
    db.commit()
    return None
