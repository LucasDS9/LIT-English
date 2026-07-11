"""
Modelos do banco de dados.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    professor = "professor"
    aluno = "aluno"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    whatsapp = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.aluno)
    is_approved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    assignments = relationship(
        "FlashcardAssignment", cascade="all, delete-orphan", passive_deletes=True, backref="flashcard"
    )

    @property
    def students(self):
        return [a.student for a in self.assignments]


class FlashcardAssignment(Base):
    """Define para qual(is) aluno(s) um flashcard é direcionado."""
    __tablename__ = "flashcard_assignments"
    __table_args__ = (UniqueConstraint("flashcard_id", "student_id", name="uq_flashcard_student"),)

    id = Column(Integer, primary_key=True, index=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("User")


class CardProgress(Base):
    __tablename__ = "card_progress"
    __table_args__ = (UniqueConstraint("student_id", "flashcard_id", name="uq_student_card"),)

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False)
    repetitions = Column(Integer, default=0, nullable=False)
    interval_days = Column(Integer, default=0, nullable=False)
    ease_factor = Column(Float, default=2.5, nullable=False)
    next_review = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_reviewed = Column(DateTime, nullable=True)
    flashcard = relationship("Flashcard")


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False)
    reviewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ReadingLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ReadingText(Base):
    __tablename__ = "reading_texts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    level = Column(Enum(ReadingLevel), nullable=False, default=ReadingLevel.A1)
    content = Column(Text, nullable=False)
    translation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assignments = relationship(
        "TextAssignment", cascade="all, delete-orphan", passive_deletes=True, backref="text"
    )

    @property
    def students(self):
        return [a.student for a in self.assignments]


class TextAssignment(Base):
    """Define para qual(is) aluno(s) um texto é direcionado."""
    __tablename__ = "text_assignments"
    __table_args__ = (UniqueConstraint("text_id", "student_id", name="uq_text_student"),)

    id = Column(Integer, primary_key=True, index=True)
    text_id = Column(Integer, ForeignKey("reading_texts.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("User")


class ExerciseType(str, enum.Enum):
    fill_blank = "fill_blank"
    word_choice = "word_choice"
    speaking = "speaking"
    translate = "translate"


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, default="")
    type = Column(Enum(ExerciseType), nullable=False)
    part1 = Column(Text, nullable=True)
    part2 = Column(Text, nullable=True)
    prompt = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=False)
    translation = Column(Text, nullable=True)
    word_choices = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Lote de envio ─────────────────────────────────────────────────────────────
# Um lote agrupa N exercícios enviados numa mesma ação "Enviar" pelo professor.
# O nome padrão é o título do primeiro exercício do lote.

class ExerciseBatch(Base):
    """Lote de exercícios enviados de uma vez."""
    __tablename__ = "exercise_batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)          # editável pelo professor
    sent_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("ExerciseBatchItem", cascade="all, delete-orphan", passive_deletes=True, backref="batch")
    student_links = relationship("ExerciseBatchStudent", cascade="all, delete-orphan", passive_deletes=True, backref="batch")


class ExerciseBatchItem(Base):
    """Exercício pertencente a um lote."""
    __tablename__ = "exercise_batch_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("exercise_batches.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)

    exercise = relationship("Exercise")


class ExerciseBatchStudent(Base):
    """Aluno que recebeu um lote."""
    __tablename__ = "exercise_batch_students"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("exercise_batches.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    student = relationship("User")


class ExerciseAssignment(Base):
    """Exercise sent from professor to a specific student."""
    __tablename__ = "exercise_assignments"

    id = Column(Integer, primary_key=True, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    next_available = Column(DateTime, nullable=True)

    student = relationship("User")
    exercise = relationship("Exercise")


class ExerciseSubmission(Base):
    __tablename__ = "exercise_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    answer = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Quando o professor clica em "OK — Visualizado", o grupo (aluno+dia) inteiro
    # é marcado como dismissed e some definitivamente da lista de Submissões.
    dismissed_by_professor = Column(Boolean, default=False, nullable=False)

    student = relationship("User")
    exercise = relationship("Exercise")


class QAQuestion(Base):
    __tablename__ = "qa_questions"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    queue_position = Column(Integer, nullable=False, default=0)


class QAAnswerLog(Base):
    __tablename__ = "qa_answer_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("qa_questions.id", ondelete="SET NULL"), nullable=True)
    question_text = Column(Text, nullable=False)
    student_answer = Column(Text, nullable=False)
    translation = Column(Text, nullable=True)
    flashcard_id = Column(Integer, ForeignKey("flashcards.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("User")
    question = relationship("QAQuestion")
    flashcard = relationship("Flashcard")


class ExerciseProgress(Base):
    __tablename__ = "exercise_progress"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    correct_streak = Column(Integer, default=0)
    next_review = Column(DateTime, default=datetime.utcnow)
    last_reviewed = Column(DateTime, nullable=True)

    student = relationship("User")
    exercise = relationship("Exercise")


# ── Métricas da tela inicial do aluno (LIT Points / Tempo de Texto) ──────────

class LitPointLog(Base):
    """
    Registra eventos de LIT Points que não podem ser recalculados a partir de
    outras tabelas (bônus por concluir todas as atividades do dia). Os pontos
    "base" de exercícios, flashcards e textos são derivados diretamente das
    tabelas existentes (exercise_submissions, review_logs, reading_time_logs)
    no momento da consulta, para refletir sempre o dado real e persistido.
    """
    __tablename__ = "lit_point_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    points = Column(Integer, nullable=False)
    source = Column(String, nullable=False)  # ex.: "exercise_daily_bonus", "flashcard_daily_bonus"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    student = relationship("User")


class ReadingTimeLog(Base):
    """Incrementos de tempo ativo de leitura/escuta (Read and Listen), enviados
    periodicamente pelo frontend enquanto o aluno tem um texto aberto."""
    __tablename__ = "reading_time_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text_id = Column(Integer, ForeignKey("reading_texts.id", ondelete="SET NULL"), nullable=True)
    seconds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    student = relationship("User")

