"""
Rotas da tela inicial (Dashboard) do aluno:
- GET  /dashboard/metrics          -> métricas consolidadas (taxa de acerto,
                                       eficiência, LIT Points, exercícios
                                       feitos, tempo de texto, flashcards)
- POST /dashboard/reading-heartbeat -> registra tempo ativo de leitura/escuta
                                       de um texto e concede LIT Points
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user
from app.database import get_db
from app.lit_points import (
    DAILY_EXERCISE_LIMIT,
    POINTS_PER_TEXT_BLOCK,
    TEXT_BLOCK_SECONDS,
    bonus_points_total,
    compute_exercise_stats,
    due_exercises_count,
    flashcard_points_total,
)
from app.models import ExerciseSubmission, ReadingTimeLog, User
from app.schemas import DashboardMetricsOut, ReadingHeartbeatIn, ReadingHeartbeatOut
from app.timezone import start_of_day_brazil_utc

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def build_dashboard_metrics(db: Session, student_id: int) -> DashboardMetricsOut:
    """Monta as métricas consolidadas de um aluno (taxa de acerto, eficiência,
    LIT Points, exercícios, tempo de texto, flashcards). Reutilizado tanto
    pela tela inicial do próprio aluno quanto pela tela de detalhes do
    professor (Configurações > Ver detalhes)."""

    # ---- Exercícios: taxa de acerto + eficiência + pontos, numa só passada ----
    ex_stats = compute_exercise_stats(db, student_id)
    total_submissions = ex_stats["total_submissions"]
    correct_submissions = ex_stats["correct_submissions"]
    accuracy_rate = round((correct_submissions / total_submissions) * 100) if total_submissions else 0

    performance_points = ex_stats["points_obtained"]
    performance_max = ex_stats["points_max"] or 100  # evita "0/0"; sem respostas ainda = 0/100

    # ---- Exercícios feitos hoje / total ----
    start_today = start_of_day_brazil_utc()
    exercises_total = total_submissions

    exercises_today = (
        db.query(ExerciseSubmission)
        .filter(
            ExerciseSubmission.student_id == student_id,
            ExerciseSubmission.created_at >= start_today,
        )
        .count()
    )
    # A meta do dia respeita o limite diário de exercícios (acúmulo do que
    # exceder o limite é mostrado nos dias seguintes, não no mesmo dia).
    exercises_today_target = min(
        DAILY_EXERCISE_LIMIT,
        exercises_today + due_exercises_count(db, student_id),
    )

    # ---- Flashcards revisados + pontos ----
    flashcard_points, flashcards_reviewed = flashcard_points_total(db, student_id)

    # ---- Tempo de texto (Read and Listen) + pontos ----
    reading_seconds = (
        db.query(ReadingTimeLog)
        .with_entities(ReadingTimeLog.seconds)
        .filter(ReadingTimeLog.student_id == student_id)
        .all()
    )
    total_reading_seconds = sum(s for (s,) in reading_seconds)
    reading_minutes = total_reading_seconds // 60
    text_points = (total_reading_seconds // TEXT_BLOCK_SECONDS) * POINTS_PER_TEXT_BLOCK

    # ---- Bônus diários já concedidos (exercícios/flashcards do dia) ----
    bonus_points = bonus_points_total(db, student_id)

    lit_points = performance_points + flashcard_points + text_points + bonus_points

    return DashboardMetricsOut(
        accuracy_rate=accuracy_rate,
        performance_points=performance_points,
        performance_max=performance_max,
        lit_points=lit_points,
        exercises_today=exercises_today,
        exercises_today_target=exercises_today_target,
        exercises_total=exercises_total,
        reading_minutes=reading_minutes,
        flashcards_reviewed=flashcards_reviewed,
    )


@router.get("/metrics", response_model=DashboardMetricsOut)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_approved_user),
):
    return build_dashboard_metrics(db, user.id)


@router.post("/reading-heartbeat", response_model=ReadingHeartbeatOut)
def reading_heartbeat(
    payload: ReadingHeartbeatIn,
    text_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_approved_user),
):
    """
    Chamado periodicamente pelo frontend enquanto o aluno tem um texto aberto
    (Read and Listen). Acumula segundos de estudo ativo e concede +10 LIT
    Points a cada bloco de 2 minutos (120s) completado.
    """
    prior_total = (
        db.query(ReadingTimeLog)
        .with_entities(ReadingTimeLog.seconds)
        .filter(ReadingTimeLog.student_id == user.id)
        .all()
    )
    old_total = sum(s for (s,) in prior_total)
    new_total = old_total + payload.seconds

    db.add(ReadingTimeLog(student_id=user.id, text_id=text_id, seconds=payload.seconds))

    old_blocks = old_total // TEXT_BLOCK_SECONDS
    new_blocks = new_total // TEXT_BLOCK_SECONDS
    points_awarded = 0
    if new_blocks > old_blocks:
        # Pontos de leitura são derivados diretamente do total acumulado
        # (reading_time_logs) na consulta de métricas, não precisam de log
        # próprio — aqui só informamos ao frontend quanto foi ganho agora.
        points_awarded = (new_blocks - old_blocks) * POINTS_PER_TEXT_BLOCK

    db.commit()

    return ReadingHeartbeatOut(total_seconds=new_total, points_awarded=points_awarded)
