"""
Fila global de atividades do aluno (curso padrão / access_type=padrao).

Prioridade:
  1. Exercícios de listas atribuídas pelo professor (lote mais recente primeiro;
     dentro do lote, ordem de envio; concluir o lote antes do próximo).
  2. Outros exercícios pendentes (revisões SM-2 de exercícios).
  3. Flashcards devidos (SM-2) — apenas quando não há exercícios pendentes.

Não altera datas nem lógica interna do SM-2 de flashcards; apenas adia a
exibição enquanto houver exercício prioritário.

Aplica-se somente a alunos do curso normal (padrao). Acesso Especial não usa
esta fila. Listas = ExerciseBatch criado pela tela do professor (assign/resend).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.lit_points import DAILY_EXERCISE_LIMIT, DAILY_EXERCISE_LIMIT_WITH_BACKLOG
from app.models import (
    AccessType,
    Exercise,
    ExerciseAssignment,
    ExerciseBatch,
    ExerciseBatchItem,
    ExerciseBatchStudent,
    ExerciseProgress,
    ExerciseSubmission,
    User,
    UserRole,
)
from app.timezone import start_of_day_brazil_utc, utcnow


def uses_global_activity_priority(student: User) -> bool:
    """Somente alunos aprovados do curso padrão."""
    return (
        student.role == UserRole.aluno
        and student.access_type == AccessType.padrao
    )


def _submitted_exercise_ids(db: Session, student_id: int) -> set[int]:
    rows = (
        db.query(ExerciseSubmission.exercise_id)
        .filter(ExerciseSubmission.student_id == student_id)
        .distinct()
        .all()
    )
    return {ex_id for (ex_id,) in rows}


def _student_batches_newest_first(db: Session, student_id: int) -> list[ExerciseBatch]:
    return (
        db.query(ExerciseBatch)
        .join(ExerciseBatchStudent, ExerciseBatchStudent.batch_id == ExerciseBatch.id)
        .filter(ExerciseBatchStudent.student_id == student_id)
        .order_by(ExerciseBatch.sent_at.desc(), ExerciseBatch.id.desc())
        .all()
    )


def _batch_exercise_ids_ordered(batch: ExerciseBatch) -> list[int]:
    return [item.exercise_id for item in sorted(batch.items, key=lambda item: item.id)]


def get_active_professor_batch(db: Session, student_id: int) -> ExerciseBatch | None:
    """
    Lote do professor mais recente que ainda tenha exercício sem nenhuma
    resposta do aluno (primeira passagem incompleta).
    """
    submitted = _submitted_exercise_ids(db, student_id)
    for batch in _student_batches_newest_first(db, student_id):
        ordered_ids = _batch_exercise_ids_ordered(batch)
        if any(ex_id not in submitted for ex_id in ordered_ids):
            return batch
    return None


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


def _exercises_by_ids(db: Session, exercise_ids: list[int]) -> dict[int, Exercise]:
    if not exercise_ids:
        return {}
    rows = db.query(Exercise).filter(Exercise.id.in_(exercise_ids)).all()
    return {ex.id: ex for ex in rows}


def _pending_batch_exercises(
    db: Session,
    student_id: int,
    batch: ExerciseBatch,
    *,
    assigned_ids: set[int],
    not_due_ids: set[int],
) -> list[Exercise]:
    submitted = _submitted_exercise_ids(db, student_id)
    by_id = _exercises_by_ids(db, _batch_exercise_ids_ordered(batch))
    pending: list[Exercise] = []
    for ex_id in _batch_exercise_ids_ordered(batch):
        if ex_id in submitted:
            continue
        if ex_id not in assigned_ids:
            continue
        if ex_id in not_due_ids:
            continue
        exercise = by_id.get(ex_id)
        if exercise:
            pending.append(exercise)
    return pending


def _other_due_exercises_sorted(
    db: Session,
    student_id: int,
    *,
    assigned_ids: set[int],
    not_due_ids: set[int],
) -> list[Exercise]:
    """Exercícios devidos fora da regra de primeiro lote incompleto."""
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
            return (0, earliest_assigned_at.get(ex.id) or ex.created_at)
        return (1, progress.next_review or ex.created_at)

    exercises.sort(key=sort_key)
    return exercises


def pending_exercises_count(db: Session, student: User) -> int:
    """Quantos exercícios pendentes existem (ignora limite diário de exibição)."""
    if not uses_global_activity_priority(student):
        from app.lit_points import due_exercises_count

        return due_exercises_count(db, student.id)

    now = utcnow()
    student_id = student.id
    assigned_ids = _assigned_exercise_ids(db, student_id)
    not_due_ids = _not_due_exercise_ids(db, student_id, now)

    active_batch = get_active_professor_batch(db, student_id)
    if active_batch:
        return len(
            _pending_batch_exercises(
                db,
                student_id,
                active_batch,
                assigned_ids=assigned_ids,
                not_due_ids=not_due_ids,
            )
        )

    return len(
        _other_due_exercises_sorted(
            db,
            student_id,
            assigned_ids=assigned_ids,
            not_due_ids=not_due_ids,
        )
    )


def should_defer_flashcards(db: Session, student: User) -> bool:
    """Flashcards aguardam enquanto houver exercício pendente (curso padrão)."""
    if not uses_global_activity_priority(student):
        return False
    return pending_exercises_count(db, student) > 0


def build_student_exercise_queue(db: Session, student: User) -> list[Exercise]:
    """
    Fila de exercícios para GET /exercises/my-assignments, respeitando
    prioridade global e limite diário.
    """
    now = utcnow()
    student_id = student.id
    assigned_ids = _assigned_exercise_ids(db, student_id)
    not_due_ids = _not_due_exercise_ids(db, student_id, now)

    if not uses_global_activity_priority(student):
        due_exercises = _other_due_exercises_sorted(
            db,
            student_id,
            assigned_ids=assigned_ids,
            not_due_ids=not_due_ids,
        )
        remaining_quota = _remaining_daily_quota(db, student_id, len(due_exercises))
        return due_exercises[:remaining_quota]

    active_batch = get_active_professor_batch(db, student_id)
    if active_batch:
        queue = _pending_batch_exercises(
            db,
            student_id,
            active_batch,
            assigned_ids=assigned_ids,
            not_due_ids=not_due_ids,
        )
    else:
        queue = _other_due_exercises_sorted(
            db,
            student_id,
            assigned_ids=assigned_ids,
            not_due_ids=not_due_ids,
        )

    remaining_quota = _remaining_daily_quota(db, student_id, len(queue))
    if remaining_quota == 0:
        return []
    return queue[:remaining_quota]


def resolve_next_activity(db: Session, student: User) -> dict:
    """
    Próxima atividade recomendada ao entrar na plataforma.
    Retorna dict serializável (NextActivityOut).
    """
    if not uses_global_activity_priority(student):
        return {"activity": "none", "url": None, "message": None}

    if pending_exercises_count(db, student) > 0:
        active = get_active_professor_batch(db, student.id)
        if active:
            message = f'Você tem exercícios pendentes da lista "{active.name}".'
        else:
            message = "Você tem exercícios pendentes para revisar."
        return {
            "activity": "exercises",
            "url": "exercicios.html",
            "message": message,
        }

    from app.lit_points import due_flashcards_count

    if due_flashcards_count(db, student.id) > 0:
        return {
            "activity": "flashcards",
            "url": "revisar.html",
            "message": "Há flashcards prontos para revisão.",
        }

    return {"activity": "none", "url": None, "message": None}
