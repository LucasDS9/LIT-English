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
    AccessType,
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
    VocabWord,
    VocabWordAssignment,
)
from app.routers.dashboard import build_dashboard_metrics
from app.routers.vocab_words import student_language
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
    access_type: str | None = None,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Lista todos os alunos cadastrados (aprovados e pendentes).

    `access_type` (opcional: "padrao" ou "especial") filtra pra só um dos
    dois grupos — usado nas telas de envio de conteúdo (Flashcards, Read and
    Listen) pra não misturar aluno de "Acesso Especial" (ex.: italiano) com
    quem faz o curso normal (inglês), já que o conteúdo desses módulos ainda
    não é separado por língua.
    """
    query = db.query(User).filter(User.role == UserRole.aluno)
    if access_type:
        try:
            query = query.filter(User.access_type == AccessType(access_type))
        except ValueError:
            pass
    return query.order_by(User.created_at.desc()).all()


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
    """Aprova o acesso de um aluno.

    Também atribui a ele, automaticamente, todas as palavras já cadastradas
    na tela Aprender **na língua dele** — curso normal (access_type=padrao)
    recebe as palavras de "ingles"; aluno de Acesso Especial recebe as da
    língua escolhida no cadastro (target_language, ex.: "italiano"). Assim
    o vocabulário fica "nativo" sem misturar línguas, e sem o professor
    precisar selecionar aluno por aluno.
    """
    student = _get_student_or_404(student_id, db)
    student.is_approved = True

    language = student_language(student)
    already_assigned = {
        row[0]
        for row in db.query(VocabWordAssignment.word_id)
        .filter(VocabWordAssignment.student_id == student.id)
        .all()
    }
    matching_word_ids = [
        row[0]
        for row in db.query(VocabWord.id).filter(VocabWord.language == language).all()
    ]
    for word_id in matching_word_ids:
        if word_id not in already_assigned:
            db.add(VocabWordAssignment(word_id=word_id, student_id=student.id))

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
