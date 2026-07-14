"""
Regras de LIT Points e métricas derivadas (usadas pela tela inicial do aluno).

Pontuação por exercício acertado (ver README de LIT Points do professor):
    Novo acertado                      -> 10 pts
    Já errou 1 vez antes                -> 8 pts
    Já errou 2+ vezes antes             -> 6 pts
    Já acertou 1 vez antes              -> 5 pts
    Já acertou 2+ vezes antes           -> 3 pts
Exercícios errados não pontuam.

Bônus:
    Concluir todos os exercícios do dia -> +50 pts (uma vez por dia)
    Concluir todos os flashcards do dia -> +15 pts (uma vez por dia)
    Flashcard revisado                  -> +2 pts (cada revisão)
    Leitura/escuta ativa de textos       -> +10 pts a cada 2 minutos
"""
from sqlalchemy.orm import Session

from app.models import (
    CardProgress,
    Exercise,
    ExerciseAssignment,
    ExerciseProgress,
    ExerciseSubmission,
    Flashcard,
    FlashcardAssignment,
    LitPointLog,
    ReviewLog,
)
from app.timezone import start_of_day_brazil_utc, utcnow

POINTS_NEW_CORRECT = 10
POINTS_AFTER_1_WRONG = 8
POINTS_AFTER_2PLUS_WRONG = 6
POINTS_AFTER_1_CORRECT = 5
POINTS_AFTER_2PLUS_CORRECT = 3
MAX_POINTS_PER_EXERCISE = 10

POINTS_PER_FLASHCARD_REVIEW = 2
POINTS_PER_TEXT_BLOCK = 10
TEXT_BLOCK_SECONDS = 120

DAILY_EXERCISE_BONUS = 50
DAILY_FLASHCARD_BONUS = 15

# Quantidade máxima de exercícios exibidos ao aluno por dia. O que exceder o
# limite não se perde: permanece devido e é mostrado nos dias seguintes.
DAILY_EXERCISE_LIMIT = 10


def points_for_correct_submission(prior_correct: int, prior_incorrect: int) -> int:
    """Pontos ganhos por UM acerto, dado o histórico anterior desse mesmo
    exercício para o aluno (sem contar a tentativa atual)."""
    if prior_correct == 0 and prior_incorrect == 0:
        return POINTS_NEW_CORRECT
    if prior_correct >= 1:
        return POINTS_AFTER_1_CORRECT if prior_correct == 1 else POINTS_AFTER_2PLUS_CORRECT
    return POINTS_AFTER_1_WRONG if prior_incorrect == 1 else POINTS_AFTER_2PLUS_WRONG


def compute_exercise_stats(db: Session, student_id: int) -> dict:
    """
    Percorre cronologicamente todas as respostas de exercícios do aluno e
    calcula, numa única consulta:
      - total de respostas e acertos (taxa de acerto)
      - pontos obtidos / máximos (eficiência)
      - total de LIT Points ganhos com exercícios
    """
    rows = (
        db.query(
            ExerciseSubmission.exercise_id,
            ExerciseSubmission.is_correct,
        )
        .filter(ExerciseSubmission.student_id == student_id)
        .order_by(ExerciseSubmission.created_at.asc())
        .all()
    )

    history: dict[int, dict[str, int]] = {}
    total_points = 0
    correct_count = 0

    for exercise_id, is_correct in rows:
        h = history.setdefault(exercise_id, {"correct": 0, "incorrect": 0})
        if is_correct:
            total_points += points_for_correct_submission(h["correct"], h["incorrect"])
            h["correct"] += 1
            correct_count += 1
        else:
            h["incorrect"] += 1

    total = len(rows)
    return {
        "total_submissions": total,
        "correct_submissions": correct_count,
        "points_obtained": total_points,
        "points_max": total * MAX_POINTS_PER_EXERCISE,
    }


def due_exercises_count(db: Session, student_id: int) -> int:
    """Quantos exercícios atribuídos ao aluno estão disponíveis agora (não
    aguardando a próxima janela de revisão espaçada)."""
    now = utcnow()
    assigned_ids = db.query(ExerciseAssignment.exercise_id).filter(
        ExerciseAssignment.student_id == student_id
    )
    not_due_ids = db.query(ExerciseProgress.exercise_id).filter(
        ExerciseProgress.student_id == student_id,
        ExerciseProgress.next_review > now,
    )
    return (
        db.query(Exercise.id)
        .filter(Exercise.id.in_(assigned_ids))
        .filter(~Exercise.id.in_(not_due_ids))
        .count()
    )


def due_flashcards_count(db: Session, student_id: int) -> int:
    """Quantos flashcards atribuídos ao aluno estão disponíveis agora para
    revisão (ignora o limite de cards por janela de 12h, usado só na fila)."""
    now = utcnow()
    assigned_ids = db.query(FlashcardAssignment.flashcard_id).filter(
        FlashcardAssignment.student_id == student_id
    )
    not_due_ids = db.query(CardProgress.flashcard_id).filter(
        CardProgress.student_id == student_id,
        CardProgress.next_review > now,
    )
    return (
        db.query(Flashcard.id)
        .filter(Flashcard.id.in_(assigned_ids))
        .filter(~Flashcard.id.in_(not_due_ids))
        .count()
    )


def has_bonus_today(db: Session, student_id: int, source: str) -> bool:
    start = start_of_day_brazil_utc()
    return (
        db.query(LitPointLog.id)
        .filter(
            LitPointLog.student_id == student_id,
            LitPointLog.source == source,
            LitPointLog.created_at >= start,
        )
        .first()
        is not None
    )


def award_daily_bonus_if_new(db: Session, student_id: int, source: str, points: int) -> bool:
    """Concede o bônus diário (uma vez por dia, por fonte) se ainda não foi
    concedido hoje. Não faz commit — quem chama é responsável por isso."""
    if has_bonus_today(db, student_id, source):
        return False
    db.add(LitPointLog(student_id=student_id, points=points, source=source))
    return True


def maybe_award_exercise_daily_bonus(db: Session, student_id: int) -> None:
    """Chamar depois de registrar uma resposta de exercício: se não sobrar
    nenhum exercício pendente hoje, concede o bônus diário (uma vez)."""
    if due_exercises_count(db, student_id) == 0:
        award_daily_bonus_if_new(db, student_id, "exercise_daily_bonus", DAILY_EXERCISE_BONUS)


def maybe_award_flashcard_daily_bonus(db: Session, student_id: int) -> None:
    """Chamar depois de registrar uma revisão de flashcard: se não sobrar
    nenhum flashcard pendente hoje, concede o bônus diário (uma vez)."""
    if due_flashcards_count(db, student_id) == 0:
        award_daily_bonus_if_new(db, student_id, "flashcard_daily_bonus", DAILY_FLASHCARD_BONUS)


def bonus_points_total(db: Session, student_id: int) -> int:
    total = (
        db.query(LitPointLog)
        .with_entities(LitPointLog.points)
        .filter(LitPointLog.student_id == student_id)
        .all()
    )
    return sum(p for (p,) in total)


def flashcard_points_total(db: Session, student_id: int) -> int:
    reviewed = db.query(ReviewLog).filter(ReviewLog.student_id == student_id).count()
    return reviewed * POINTS_PER_FLASHCARD_REVIEW, reviewed
