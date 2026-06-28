"""
Rotas de QA — uso exclusivo do professor:
- Cadastrar perguntas em lote (cola uma lista, uma por linha)
- Sortear uma pergunta aleatória pra fazer ao aluno
- Salvar a resposta falada do aluno (gera um Flashcard automaticamente, que
  alimenta "Meu Vocabulário")
- Ver o histórico de respostas registradas
"""
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_professor
from app.database import get_db
from app.models import Flashcard, QAAnswerLog, QAQuestion, User, UserRole
from app.schemas import (
    QAAnswerLogOut,
    QAAnswerSave,
    QAQuestionBulkCreate,
    QAQuestionOut,
    QARandomQuestionOut,
)

router = APIRouter(prefix="/qa", tags=["QA (Professor)"])


# ============================================================
# Banco de perguntas
# ============================================================

@router.post("/questions/bulk", response_model=list[QAQuestionOut], status_code=status.HTTP_201_CREATED)
def add_questions_bulk(
    data: QAQuestionBulkCreate,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Recebe um texto com várias perguntas (uma por linha) e cadastra todas de uma vez."""
    lines = [line.strip() for line in data.questions_text.splitlines()]
    lines = [line for line in lines if line]  # ignora linhas vazias

    if not lines:
        raise HTTPException(status_code=400, detail="Nenhuma pergunta válida encontrada no texto.")

    last = db.query(QAQuestion).order_by(QAQuestion.queue_position.desc()).first()
    max_position = last.queue_position if last else 0

    created = []
    for line in lines:
        max_position += 1
        question = QAQuestion(question=line, queue_position=max_position)
        db.add(question)
        created.append(question)

    db.commit()
    for question in created:
        db.refresh(question)
    return created


@router.get("/questions", response_model=list[QAQuestionOut])
def list_questions(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista todas as perguntas cadastradas no banco de QA, na ordem da fila."""
    return db.query(QAQuestion).order_by(QAQuestion.queue_position.asc()).all()


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    question = db.query(QAQuestion).filter(QAQuestion.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")

    # Mantém o histórico de respostas já dadas a esta pergunta, só
    # desvincula (question_text já guarda o texto da pergunta).
    db.query(QAAnswerLog).filter(QAAnswerLog.question_id == question_id).update(
        {QAAnswerLog.question_id: None}
    )

    db.delete(question)
    db.commit()
    return None


@router.get("/questions/random", response_model=QARandomQuestionOut)
def get_random_question(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Sorteia uma pergunta aleatória do banco cadastrado pelo professor."""
    questions = db.query(QAQuestion).all()
    if not questions:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma pergunta cadastrada ainda. Cole sua lista em /qa/questions/bulk.",
        )
    chosen = random.choice(questions)
    return QARandomQuestionOut(question_id=chosen.id, question=chosen.question)


@router.post("/questions/{question_id}/swap", response_model=QARandomQuestionOut)
def swap_question(
    question_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Troca a pergunta exibida: manda a pergunta atual para o final da fila e
    retorna a próxima pergunta (a de menor posição na fila).
    """
    current = db.query(QAQuestion).filter(QAQuestion.id == question_id).first()
    if not current:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")

    last = db.query(QAQuestion).order_by(QAQuestion.queue_position.desc()).first()
    current.queue_position = (last.queue_position if last else 0) + 1
    db.commit()

    next_question = (
        db.query(QAQuestion)
        .order_by(QAQuestion.queue_position.asc())
        .first()
    )
    if not next_question:
        raise HTTPException(status_code=404, detail="Nenhuma pergunta cadastrada.")

    return QARandomQuestionOut(question_id=next_question.id, question=next_question.question)


# ============================================================
# Resposta do aluno (registrada pelo professor) + histórico
# ============================================================

@router.post("/answers", response_model=QAAnswerLogOut, status_code=status.HTTP_201_CREATED)
def save_answer(
    data: QAAnswerSave,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """
    Salva o que o aluno respondeu em voz alta para a pergunta exibida.
    Também cria um Flashcard automaticamente (front=resposta do aluno,
    back=tradução/contexto), pra alimentar 'Meu Vocabulário'.
    """
    students = db.query(User).filter(User.role == UserRole.aluno, User.is_approved == True).all()
    if not students:
        raise HTTPException(status_code=404, detail="Nenhum aluno aprovado.")

    target_students = students if data.student_id is None else [s for s in students if s.id == data.student_id]
    if not target_students:
        raise HTTPException(status_code=404, detail="Aluno não encontrado.")

    created_log=None
    for student in target_students:
        back_text = data.translation.strip() if data.translation else data.question_text
        flashcard = Flashcard(front=data.student_answer, back=back_text)
        db.add(flashcard)
        db.flush()
        log = QAAnswerLog(
        student_id=student.id,
        question_id=data.question_id,
        question_text=data.question_text,
        student_answer=data.student_answer,
        translation=data.translation,
        flashcard_id=flashcard.id,
    )
        db.add(log)
        created_log=log
    db.commit()
    db.refresh(created_log)
    return created_log


@router.get("/answers", response_model=list[QAAnswerLogOut])
def list_answers(
    student_id: int | None = None,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Histórico de respostas registradas no QA, opcionalmente filtrado por aluno."""
    query = db.query(QAAnswerLog)
    if student_id is not None:
        query = query.filter(QAAnswerLog.student_id == student_id)
    return query.order_by(QAAnswerLog.created_at.desc()).all()
