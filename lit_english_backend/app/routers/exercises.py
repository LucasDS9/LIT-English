"""
Rotas de Exercícios:
- Professor: criar, listar, deletar, atribuir a alunos
- Aluno: ver exercícios atribuídos, responder
"""
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.models import Exercise, ExerciseAssignment, ExerciseSubmission, ExerciseProgress, User, UserRole
from app.routers.pronunciation import transcribe
from app.schemas import (
    ExerciseAnswerResult,
    ExerciseAnswerSubmit,
    ExerciseAssignPayload,
    ExerciseCreate,
    ExerciseOut,
    ExercisePracticeOut,
    ExerciseProgressItemOut,
    ExerciseSubmissionDayOut,
    ExerciseSubmissionItemOut,
)
from app.timezone import brazil_date_key, start_of_next_day_brazil_utc, utcnow

router = APIRouter(prefix="/exercises", tags=["Exercícios"])


def _normalize(text: str) -> str:
    return text.strip().lower().rstrip(".,!?")


def _schedule_after_submit(progress,is_correct):
    progress.correct_streak = progress.correct_streak or 0
    if is_correct:
        progress.correct_streak += 1
        days={1:1,2:4,3:10,4:20}.get(progress.correct_streak,45)
    else:
        progress.correct_streak = 0
        days=1
    progress.last_reviewed=utcnow()
    progress.next_review=utcnow()+timedelta(days=days)


def _get_assignment(db: Session, student_id: int, exercise_id: int) -> ExerciseAssignment | None:
    return (
        db.query(ExerciseAssignment)
        .filter(
            ExerciseAssignment.student_id == student_id,
            ExerciseAssignment.exercise_id == exercise_id,
        )
        .order_by(ExerciseAssignment.assigned_at.desc())
        .first()
    )


# ============================================================
# PROFESSOR: CRUD
# ============================================================

@router.post("", response_model=ExerciseOut, status_code=status.HTTP_201_CREATED)
def create_exercise(
    data: ExerciseCreate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    exercise = Exercise(
        title=data.title,
        type=data.type,
        part1=data.part1,
        part2=data.part2,
        prompt=data.prompt,
        correct_answer=data.correct_answer,
        translation=data.translation,
        word_choices=data.word_choices,
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.get("", response_model=list[ExerciseOut])
def list_exercises_admin(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    # Retorna apenas exercícios que ainda NÃO foram enviados a nenhum aluno
    assigned_ids = db.query(ExerciseAssignment.exercise_id).distinct().subquery()
    return (
        db.query(Exercise)
        .filter(~Exercise.id.in_(assigned_ids))
        .order_by(Exercise.created_at.desc())
        .all()
    )


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercício não encontrado.")
    db.delete(exercise)
    db.commit()
    return None


# ============================================================
# PROFESSOR: atribuir exercícios a aluno
# ============================================================

@router.post("/assign", status_code=status.HTTP_201_CREATED)
def assign_exercises(
    payload: ExerciseAssignPayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    student = db.query(User).filter(User.id == payload.student_id, User.role == "aluno").first()
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")

    now = utcnow()
    created = 0
    for ex_id in payload.exercise_ids:
        exercise = db.query(Exercise).filter(Exercise.id == ex_id).first()
        if not exercise:
            continue
        assignment = ExerciseAssignment(
            exercise_id=ex_id,
            student_id=payload.student_id,
            assigned_at=now,
            next_available=now,
        )
        db.add(assignment)
        created += 1

    db.commit()
    return {"assigned": created}


# ============================================================
# PROFESSOR: submissões dos alunos (agrupadas por dia)
# ============================================================

@router.get("/submissions", response_model=list[ExerciseSubmissionDayOut])
def list_submissions(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    query = (
        db.query(ExerciseSubmission)
        .join(User, ExerciseSubmission.student_id == User.id)
        .join(Exercise, ExerciseSubmission.exercise_id == Exercise.id)
    )
    if student_id is not None:
        query = query.filter(ExerciseSubmission.student_id == student_id)

    submissions = query.order_by(ExerciseSubmission.created_at.desc()).all()

    groups: dict[tuple[int, str], list] = defaultdict(list)
    names: dict[int, str] = {}

    for s in submissions:
        day_key = brazil_date_key(s.created_at)
        groups[(s.student_id, day_key)].append(s)
        names[s.student_id] = s.student.name

    result = []
    for (sid, day_key), items in groups.items():
        items.sort(key=lambda x: x.created_at)
        result.append(
            ExerciseSubmissionDayOut(
                student_id=sid,
                student_name=names[sid],
                date=day_key,
                submissions=[
                    ExerciseSubmissionItemOut(
                        exercise_title=item.exercise.title,
                        exercise_type=item.exercise.type,
                        exercise_prompt=item.exercise.prompt,
                        answer=item.answer,
                        is_correct=item.is_correct,
                        created_at=item.created_at,
                    )
                    for item in items
                ],
                total=len(items),
                correct_count=sum(1 for item in items if item.is_correct),
            )
        )

    result.sort(key=lambda g: (g.date, max(s.created_at for s in g.submissions)), reverse=True)
    return result


@router.get("/student-progress/{student_id}", response_model=list[ExerciseProgressItemOut])
def get_student_exercise_progress(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Retorna o status de revisão espaçada de todos os exercícios atribuídos
    a um aluno específico — visível apenas para o professor.
    """
    student = db.query(User).filter(User.id == student_id, User.role == UserRole.aluno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")

    now = utcnow()

    # Exercícios atribuídos ao aluno
    assigned_ids = (
        db.query(ExerciseAssignment.exercise_id)
        .filter(ExerciseAssignment.student_id == student_id)
        .subquery()
    )

    exercises = (
        db.query(Exercise)
        .filter(Exercise.id.in_(assigned_ids))
        .order_by(Exercise.created_at.asc())
        .all()
    )

    # Índice de progresso por exercise_id
    progress_map = {
        p.exercise_id: p
        for p in db.query(ExerciseProgress).filter(
            ExerciseProgress.student_id == student_id
        ).all()
    }

    # Última resposta de cada exercício
    last_answer_map: dict[int, str] = {}
    for ex in exercises:
        last_sub = (
            db.query(ExerciseSubmission)
            .filter(
                ExerciseSubmission.student_id == student_id,
                ExerciseSubmission.exercise_id == ex.id,
            )
            .order_by(ExerciseSubmission.created_at.desc())
            .first()
        )
        if last_sub:
            last_answer_map[ex.id] = last_sub.answer

    result = []
    for ex in exercises:
        progress = progress_map.get(ex.id)
        next_review = progress.next_review if progress else None
        last_reviewed = progress.last_reviewed if progress else None
        correct_streak = progress.correct_streak if progress else 0
        is_due = next_review is None or next_review <= now
        result.append(
            ExerciseProgressItemOut(
                exercise_id=ex.id,
                title=ex.title,
                exercise_type=ex.type.value,
                prompt=ex.prompt,
                correct_streak=correct_streak,
                last_answer=last_answer_map.get(ex.id),
                last_reviewed=last_reviewed,
                next_review=next_review,
                is_due=is_due,
            )
        )

    return result


# ============================================================
# ALUNO: ver exercícios atribuídos e responder
# ============================================================

@router.get("/my-assignments", response_model=list[ExercisePracticeOut])
def my_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_approved_user),
):
    """
    Retorna exercícios disponíveis para revisão agora, seguindo a mesma
    filosofia de repetição espaçada dos flashcards:
    - Exercícios nunca respondidos (sem ExerciseProgress) aparecem imediatamente.
    - Exercícios já respondidos só aparecem quando next_review <= agora.
    """
    now = utcnow()

    # Subquery: IDs de exercícios atribuídos ao aluno
    assigned_ids_subquery = (
        db.query(ExerciseAssignment.exercise_id)
        .filter(ExerciseAssignment.student_id == user.id)
    )

    # Subquery: IDs de exercícios cujo next_review ainda está no futuro
    not_due_subquery = (
        db.query(ExerciseProgress.exercise_id)
        .filter(
            ExerciseProgress.student_id == user.id,
            ExerciseProgress.next_review > now,
        )
    )

    # Retorna exercícios atribuídos que estão vencidos (ou nunca respondidos)
    due_exercises = (
        db.query(Exercise)
        .filter(Exercise.id.in_(assigned_ids_subquery))
        .filter(~Exercise.id.in_(not_due_subquery))
        .order_by(Exercise.created_at.asc())
        .all()
    )

    return due_exercises


@router.post("/{exercise_id}/submit", response_model=ExerciseAnswerResult)
def submit_answer(
    exercise_id: int,
    payload: ExerciseAnswerSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_approved_user),
):
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercício não encontrado.")

    is_correct = _normalize(payload.answer) == _normalize(exercise.correct_answer)

    db.add(ExerciseSubmission(
        student_id=user.id,
        exercise_id=exercise_id,
        answer=payload.answer,
        is_correct=is_correct,
    ))

    progress = db.query(ExerciseProgress).filter(ExerciseProgress.student_id==user.id, ExerciseProgress.exercise_id==exercise_id).first()
    if not progress:
        progress=ExerciseProgress(student_id=user.id, exercise_id=exercise_id)
        db.add(progress)
    _schedule_after_submit(progress, is_correct)

    db.commit()

    return ExerciseAnswerResult(correct=is_correct, correct_answer=exercise.correct_answer)


@router.post("/{exercise_id}/submit-audio", response_model=ExerciseAnswerResult)
async def submit_audio_answer(
    exercise_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_approved_user),
):
    """
    Exercício do tipo 'speaking': o aluno grava um áudio falando a frase em
    inglês (exercise.correct_answer). O Faster-Whisper transcreve o áudio e
    comparamos a transcrição com a resposta esperada para decidir se está certo.
    """
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercício não encontrado.")

    audio_bytes = await audio.read()
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Áudio muito curto ou inválido.")

    try:
        transcribed_text = transcribe(audio_bytes, "english")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na transcrição: {e}")

    if not transcribed_text:
        transcribed_text = ""

    exp = _normalize(exercise.correct_answer)
    got = _normalize(transcribed_text)
    is_correct = exp == got

    db.add(ExerciseSubmission(
        student_id=user.id,
        exercise_id=exercise_id,
        answer=transcribed_text or "(não foi possível entender o áudio)",
        is_correct=is_correct,
    ))

    progress = db.query(ExerciseProgress).filter(ExerciseProgress.student_id==user.id, ExerciseProgress.exercise_id==exercise_id).first()
    if not progress:
        progress=ExerciseProgress(student_id=user.id, exercise_id=exercise_id)
        db.add(progress)
    _schedule_after_submit(progress, is_correct)

    db.commit()

    return ExerciseAnswerResult(
        correct=is_correct,
        correct_answer=exercise.correct_answer,
        transcribed_text=transcribed_text,
    )
