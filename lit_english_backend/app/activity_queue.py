"""
Fila de atividades do aluno.

Exercícios e flashcards são totalmente independentes, cada um com seu
próprio SM-2 — sem bloqueio cruzado nem lote/prioridade forçados.

- Exercícios: os ainda sem nenhuma resposta do aluno vêm primeiro,
  ordenados pela data em que foram atribuídos (mais recente primeiro —
  atribuiu hoje aparece antes do que foi atribuído ontem). Depois vêm
  os que já têm progresso SM-2 e estão vencidos, ordenados pela data
  de vencimento (mais antigo primeiro).
- Flashcards: cards do professor aparecem antes dos do próprio aluno
  (isso é tratado em app/routers/flashcards.py, na query de review/next).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.lit_points import (
    DAILY_EXERCISE_LIMIT,
    DAILY_EXERCISE_LIMIT_WITH_BACKLOG,
    due_exercises_count,
)
from app.models import Exercise, ExerciseAssignment, ExerciseProgress, ExerciseSubmission, User
from app.timezone import start_of_day_brazil_utc, utcnow


def _assigned_exercise_ids(db: Session, student_id: int) -> set[int]:
    rows = (
        db.query(ExerciseAssignment.exercise_id)
        .filter(ExerciseAssignment.student_id == student_id)
        .all()
    )
    return {ex_id for (ex_id,) in rows}


def _not_due_exercise_ids(db: Session, student_id: int, now) -> set[int]:
    rows = (
        db.query(ExerciseProgress.exercise_id)
        .filter(
            ExerciseProgress.student_id == student_id,
            ExerciseProgress.next_review > now,
        )
        .all()
    )
    return {ex_id for (ex_id,) in rows}


def _remaining_daily_quota(db: Session, student_id: int, due_count: int) -> int:
    start_today = start_of_day_brazil_utc()
    answered_today = (
        db.query(ExerciseSubmission)
        .filter(
            ExerciseSubmission.student_id == student_id,
            ExerciseSubmission.created_at >= start_today,
        )
        .count()
    )
    daily_limit = (
        DAILY_EXERCISE_LIMIT_WITH_BACKLOG
        if due_count > DAILY_EXERCISE_LIMIT
        else DAILY_EXERCISE_LIMIT
    )
    return max(0, daily_limit - answered_today)


def _due_exercises_sorted(
    db: Session,
    student_id: int,
    *,
    assigned_ids: set[int],
    not_due_ids: set[int],
) -> list[Exercise]:
    """
    Exercícios pendentes do aluno: novos (sem progresso SM-2) primeiro,
    ordenados por data de atribuição decrescente (mais recente primeiro);
    depois os já vencidos (com progresso SM-2), por data de vencimento
    crescente (mais antigo primeiro).
    """
    due_ids = [ex_id for ex_id in assigned_ids if ex_id not in not_due_ids]
    if not due_ids:
        return []

    progress_by_exercise = {
        p.exercise_id: p
        for p in db.query(ExerciseProgress).filter(ExerciseProgress.student_id == student_id).all()
    }

    earliest_assigned_at: dict[int, object] = {}
    for assignment in (
        db.query(ExerciseAssignment)
        .filter(ExerciseAssignment.student_id == student_id)
        .all()
    ):
        current = earliest_assigned_at.get(assignment.exercise_id)
        if current is None or assignment.assigned_at < current:
            earliest_assigned_at[assignment.exercise_id] = assignment.assigned_at

    exercises = db.query(Exercise).filter(Exercise.id.in_(due_ids)).all()

    def sort_key(ex: Exercise):
        progress = progress_by_exercise.get(ex.id)
        if progress is None:
            assigned_at = earliest_assigned_at.get(ex.id) or ex.created_at
            return (0, -assigned_at.timestamp())
        next_review = progress.next_review or ex.created_at
        return (1, next_review.timestamp())

    exercises.sort(key=sort_key)
    return exercises


def pending_exercises_count(db: Session, student: User) -> int:
    """Quantos exercícios pendentes existem (ignora limite diário de exibição)."""
    return due_exercises_count(db, student.id)


def should_defer_flashcards(db: Session, student: User) -> bool:
    """Flashcards nunca são bloqueados por exercícios pendentes."""
    return False


def build_student_exercise_queue(db: Session, student: User) -> list[Exercise]:
    """Fila de exercícios para GET /exercises/my-assignments, respeitando o limite diário."""
    now = utcnow()
    student_id = student.id
    assigned_ids = _assigned_exercise_ids(db, student_id)
    not_due_ids = _not_due_exercise_ids(db, student_id, now)

    due_exercises = _due_exercises_sorted(
        db,
        student_id,
        assigned_ids=assigned_ids,
        not_due_ids=not_due_ids,
    )
    remaining_quota = _remaining_daily_quota(db, student_id, len(due_exercises))
    return due_exercises[:remaining_quota]


def resolve_next_activity(db: Session, student: User) -> dict:
    """
    Sem redirecionamento forçado: exercícios e flashcards são acessados
    livremente pelo aluno, sem prioridade imposta pelo sistema.
    """
    return {"activity": "none", "url": None, "message": None}
