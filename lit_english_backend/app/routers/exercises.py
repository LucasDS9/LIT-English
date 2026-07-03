"""
Rotas de Exercícios:
- Professor: criar, listar, deletar, atribuir a alunos (múltiplos)
- Aluno: ver exercícios atribuídos, responder
- Histórico de lotes: listar, renomear, reenviar
"""
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user, get_current_professor
from app.database import get_db
from app.models import (
    Exercise,
    ExerciseAssignment,
    ExerciseBatch,
    ExerciseBatchItem,
    ExerciseBatchStudent,
    ExerciseProgress,
    ExerciseSubmission,
    ExerciseType,
    User,
    UserRole,
)
from app.ai_judge import judge_answer
from app.routers.pronunciation import transcribe
from app.schemas import (
    ExerciseAnswerResult,
    ExerciseAnswerSubmit,
    ExerciseAssignPayload,
    ExerciseBatchExerciseOut,
    ExerciseBatchOut,
    ExerciseBatchRenamePayload,
    ExerciseBatchResendPayload,
    ExerciseBatchStudentOut,
    ExerciseCreate,
    ExerciseOut,
    ExercisePracticeOut,
    ExerciseProgressItemOut,
    ExerciseSubmissionDayOut,
    ExerciseSubmissionDismissPayload,
    ExerciseSubmissionItemOut,
    ExerciseUpdate,
)
from app.timezone import brazil_date_key, start_of_next_day_brazil_utc, utcnow

router = APIRouter(prefix="/exercises", tags=["Exercícios"])


def _normalize(text: str) -> str:
    return text.strip().lower().rstrip(".,!?")


def _schedule_after_submit(progress, is_correct):
    progress.correct_streak = progress.correct_streak or 0
    if is_correct:
        progress.correct_streak += 1
        days = {1: 1, 2: 4, 3: 10, 4: 20}.get(progress.correct_streak, 45)
    else:
        progress.correct_streak = 0
        days = 1
    progress.last_reviewed = utcnow()
    progress.next_review = utcnow() + timedelta(days=days)


def _exercise_context(exercise: Exercise) -> str:
    """Monta a frase completa do exercício (quando houver) para dar contexto à IA."""
    if exercise.part1 or exercise.part2:
        return f"{exercise.part1 or ''} ___ {exercise.part2 or ''}".strip()
    return exercise.prompt or ""


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


@router.patch("/{exercise_id}", response_model=ExerciseOut)
def update_exercise(
    exercise_id: int,
    payload: ExerciseUpdate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Edita um exercício existente. Como o mesmo exercício pode estar em mais
    de um lote do histórico, a edição aqui reflete em todos os lotes e em
    todas as atribuições já existentes (o aluno passa a ver a versão nova).
    """
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercício não encontrado.")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(exercise, field, value)

    db.commit()
    db.refresh(exercise)
    return exercise


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercício não encontrado.")

    # Remove tudo que referencia este exercício antes de excluí-lo
    # (atribuições, respostas enviadas, progresso espaçado e itens de lote).
    db.query(ExerciseAssignment).filter(ExerciseAssignment.exercise_id == exercise_id).delete()
    db.query(ExerciseSubmission).filter(ExerciseSubmission.exercise_id == exercise_id).delete()
    db.query(ExerciseProgress).filter(ExerciseProgress.exercise_id == exercise_id).delete()
    db.query(ExerciseBatchItem).filter(ExerciseBatchItem.exercise_id == exercise_id).delete()

    db.delete(exercise)
    db.commit()
    return None


# ============================================================
# PROFESSOR: atribuir exercícios a um ou mais alunos
# ============================================================

@router.post("/assign", status_code=status.HTTP_201_CREATED)
def assign_exercises(
    payload: ExerciseAssignPayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    # Suporte a single (student_id) e multi (student_ids)
    if payload.student_ids:
        target_ids = payload.student_ids
    elif payload.student_id is not None:
        target_ids = [payload.student_id]
    else:
        raise HTTPException(status_code=422, detail="Informe student_id ou student_ids.")

    # Valida alunos
    students = (
        db.query(User)
        .filter(User.id.in_(target_ids), User.role == "aluno")
        .all()
    )
    found_ids = {s.id for s in students}
    missing = set(target_ids) - found_ids
    if missing:
        raise HTTPException(status_code=404, detail=f"Aluno(s) não encontrado(s): {list(missing)}")

    # Determina o nome do lote (título do primeiro exercício da lista)
    first_ex = db.query(Exercise).filter(Exercise.id == payload.exercise_ids[0]).first()
    batch_name = first_ex.title if first_ex else f"Lote {utcnow().strftime('%d/%m/%Y %H:%M')}"

    now = utcnow()
    total_assigned = 0

    # Um único lote para esta ação de envio, vinculado a todos os alunos
    # selecionados — assim, no histórico, aparece um bloco só dizendo
    # para quais alunos foi enviado, em vez de um bloco repetido por aluno.
    batch = ExerciseBatch(name=batch_name, sent_at=now)
    db.add(batch)
    db.flush()  # gera batch.id

    for ex_id in payload.exercise_ids:
        exercise = db.query(Exercise).filter(Exercise.id == ex_id).first()
        if not exercise:
            continue
        db.add(ExerciseBatchItem(batch_id=batch.id, exercise_id=ex_id))

    for student_id in target_ids:
        db.add(ExerciseBatchStudent(batch_id=batch.id, student_id=student_id))

        for ex_id in payload.exercise_ids:
            exercise = db.query(Exercise).filter(Exercise.id == ex_id).first()
            if not exercise:
                continue

            assignment = ExerciseAssignment(
                exercise_id=ex_id,
                student_id=student_id,
                assigned_at=now,
                next_available=now,
            )
            db.add(assignment)
            total_assigned += 1

    db.commit()
    return {"assigned": total_assigned}


# ============================================================
# PROFESSOR: histórico de lotes
# ============================================================

@router.get("/batches", response_model=list[ExerciseBatchOut])
def list_batches(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista todos os lotes de exercícios enviados, do mais recente para o mais antigo."""
    batches = (
        db.query(ExerciseBatch)
        .order_by(ExerciseBatch.sent_at.desc())
        .all()
    )

    result = []
    for batch in batches:
        exercises = [item.exercise for item in batch.items if item.exercise]
        students = [link.student for link in batch.student_links if link.student]
        result.append(
            ExerciseBatchOut(
                batch_id=batch.id,
                batch_name=batch.name,
                sent_at=batch.sent_at,
                students=[ExerciseBatchStudentOut(id=s.id, name=s.name) for s in students],
                exercises=[
                    ExerciseBatchExerciseOut(
                        id=ex.id,
                        title=ex.title,
                        type=ex.type.value,
                        part1=ex.part1,
                        part2=ex.part2,
                        prompt=ex.prompt,
                        correct_answer=ex.correct_answer,
                        translation=ex.translation,
                        word_choices=ex.word_choices,
                    )
                    for ex in exercises
                ],
            )
        )
    return result


@router.patch("/batches/{batch_id}/rename", status_code=200)
def rename_batch(
    batch_id: int,
    payload: ExerciseBatchRenamePayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    batch = db.query(ExerciseBatch).filter(ExerciseBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
    batch.name = payload.name.strip()
    db.commit()
    return {"ok": True}


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Remove um lote do histórico. Isso NÃO revoga os exercícios já atribuídos
    aos alunos (eles continuam podendo responder); apenas o registro do
    histórico (e seus itens/vínculos de aluno) é excluído.
    """
    batch = db.query(ExerciseBatch).filter(ExerciseBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")
    db.delete(batch)
    db.commit()
    return None


@router.post("/batches/{batch_id}/resend", status_code=201)
def resend_batch(
    batch_id: int,
    payload: ExerciseBatchResendPayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Reenvia todos os exercícios de um lote para os alunos informados.
    Cria um novo lote com o mesmo nome do original.
    """
    original = db.query(ExerciseBatch).filter(ExerciseBatch.id == batch_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Lote não encontrado.")

    exercise_ids = [item.exercise_id for item in original.items]
    if not exercise_ids:
        raise HTTPException(status_code=422, detail="Lote sem exercícios.")

    students = (
        db.query(User)
        .filter(User.id.in_(payload.student_ids), User.role == "aluno")
        .all()
    )
    if not students:
        raise HTTPException(status_code=404, detail="Nenhum aluno válido informado.")

    now = utcnow()
    total = 0

    # Um único novo lote para esta ação de reenvio, vinculado a todos os
    # alunos selecionados — mesmo padrão usado em assign_exercises.
    new_batch = ExerciseBatch(name=original.name, sent_at=now)
    db.add(new_batch)
    db.flush()

    for ex_id in exercise_ids:
        exercise = db.query(Exercise).filter(Exercise.id == ex_id).first()
        if not exercise:
            continue
        db.add(ExerciseBatchItem(batch_id=new_batch.id, exercise_id=ex_id))

    for student in students:
        db.add(ExerciseBatchStudent(batch_id=new_batch.id, student_id=student.id))

        for ex_id in exercise_ids:
            exercise = db.query(Exercise).filter(Exercise.id == ex_id).first()
            if not exercise:
                continue
            db.add(ExerciseAssignment(
                exercise_id=ex_id,
                student_id=student.id,
                assigned_at=now,
                next_available=now,
            ))
            total += 1

    db.commit()
    return {"assigned": total}


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
        .filter(ExerciseSubmission.dismissed_by_professor.is_(False))
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


@router.post("/submissions/dismiss", status_code=200)
def dismiss_submissions(
    payload: ExerciseSubmissionDismissPayload,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Marca como visualizado (e remove definitivamente da lista de Submissões)
    todo o grupo aluno+dia indicado. Usado pelo botão "OK — Visualizado".
    """
    submissions = (
        db.query(ExerciseSubmission)
        .filter(ExerciseSubmission.student_id == payload.student_id)
        .all()
    )
    affected = 0
    for s in submissions:
        if brazil_date_key(s.created_at) == payload.date:
            s.dismissed_by_professor = True
            affected += 1

    db.commit()
    return {"dismissed": affected}


@router.get("/student-progress/{student_id}", response_model=list[ExerciseProgressItemOut])
def get_student_exercise_progress(
    student_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    student = db.query(User).filter(User.id == student_id, User.role == UserRole.aluno).first()
    if not student:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")

    now = utcnow()

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

    progress_map = {
        p.exercise_id: p
        for p in db.query(ExerciseProgress).filter(
            ExerciseProgress.student_id == student_id
        ).all()
    }

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
    now = utcnow()

    assigned_ids_subquery = (
        db.query(ExerciseAssignment.exercise_id)
        .filter(ExerciseAssignment.student_id == user.id)
    )

    not_due_subquery = (
        db.query(ExerciseProgress.exercise_id)
        .filter(
            ExerciseProgress.student_id == user.id,
            ExerciseProgress.next_review > now,
        )
    )

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

    reason: str | None = None
    if exercise.type == ExerciseType.word_choice:
        # Múltipla escolha: a resposta vem de uma lista fixa de opções, então
        # comparação exata é suficiente (e mais rápida) — não precisa da IA.
        is_correct = _normalize(payload.answer) == _normalize(exercise.correct_answer)
    else:
        result = judge_answer(
            expected=exercise.correct_answer,
            given=payload.answer,
            context=_exercise_context(exercise),
        )
        is_correct = result["correct"]
        reason = result["reason"]

    db.add(ExerciseSubmission(
        student_id=user.id,
        exercise_id=exercise_id,
        answer=payload.answer,
        is_correct=is_correct,
    ))

    progress = db.query(ExerciseProgress).filter(
        ExerciseProgress.student_id == user.id,
        ExerciseProgress.exercise_id == exercise_id
    ).first()
    if not progress:
        progress = ExerciseProgress(student_id=user.id, exercise_id=exercise_id)
        db.add(progress)
    _schedule_after_submit(progress, is_correct)

    db.commit()

    return ExerciseAnswerResult(correct=is_correct, correct_answer=exercise.correct_answer, reason=reason)


@router.post("/{exercise_id}/submit-audio", response_model=ExerciseAnswerResult)
async def submit_audio_answer(
    exercise_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_approved_user),
):
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

    result = judge_answer(
        expected=exercise.correct_answer,
        given=transcribed_text,
        context=_exercise_context(exercise),
    )
    is_correct = result["correct"]
    reason = result["reason"]

    db.add(ExerciseSubmission(
        student_id=user.id,
        exercise_id=exercise_id,
        answer=transcribed_text or "(não foi possível entender o áudio)",
        is_correct=is_correct,
    ))

    progress = db.query(ExerciseProgress).filter(
        ExerciseProgress.student_id == user.id,
        ExerciseProgress.exercise_id == exercise_id
    ).first()
    if not progress:
        progress = ExerciseProgress(student_id=user.id, exercise_id=exercise_id)
        db.add(progress)
    _schedule_after_submit(progress, is_correct)

    db.commit()

    return ExerciseAnswerResult(
        correct=is_correct,
        correct_answer=exercise.correct_answer,
        transcribed_text=transcribed_text,
        reason=reason,
    )
