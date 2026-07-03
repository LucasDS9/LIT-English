"""
Schemas Pydantic.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.models import ExerciseType, ReadingLevel, UserRole


# ---------- Auth ----------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    whatsapp: Optional[str] = None
    password: str
    role: UserRole = UserRole.aluno


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    whatsapp: Optional[str] = None
    role: UserRole
    is_approved: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Flashcards ----------

class FlashcardCreate(BaseModel):
    front: str
    back: str
    student_ids: List[int] = Field(min_length=1)


class FlashcardUpdate(BaseModel):
    front: Optional[str] = None
    back: Optional[str] = None
    student_ids: Optional[List[int]] = None


class FlashcardStudentOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class FlashcardOut(BaseModel):
    id: int
    front: str
    back: str
    created_at: datetime
    students: List[FlashcardStudentOut] = []

    class Config:
        from_attributes = True


# ---------- Revisão ----------

class ReviewCardOut(BaseModel):
    flashcard_id: int
    front: str
    back: str


class ReviewQueueOut(BaseModel):
    cards: list[ReviewCardOut]
    remaining_in_window: int
    limit_per_window: int


class ReviewSubmit(BaseModel):
    quality: int = Field(ge=0, le=5)


class CardProgressOut(BaseModel):
    flashcard_id: int
    repetitions: int
    interval_days: int
    ease_factor: float
    next_review: datetime

    class Config:
        from_attributes = True


class VocabularyItemOut(BaseModel):
    """Vocabulário de um aluno específico: flashcard + status de revisão."""
    flashcard_id: int
    front: str
    back: str
    next_review: Optional[datetime] = None
    is_due: bool


# ---------- Read and Listen ----------

class ReadingTextCreate(BaseModel):
    title: str
    level: ReadingLevel
    content: str
    translation: Optional[str] = None
    student_ids: List[int] = []


class ReadingTextUpdate(BaseModel):
    title: Optional[str] = None
    level: Optional[ReadingLevel] = None
    content: Optional[str] = None
    translation: Optional[str] = None
    student_ids: Optional[List[int]] = None


class ReadingTextOut(BaseModel):
    id: int
    title: str
    level: ReadingLevel
    content: str
    translation: Optional[str]
    created_at: datetime
    students: List[FlashcardStudentOut] = []

    class Config:
        from_attributes = True


# ---------- Exercícios ----------

class ExerciseCreate(BaseModel):
    title: str
    type: ExerciseType
    part1: Optional[str] = None
    part2: Optional[str] = None
    prompt: str
    correct_answer: str
    translation: Optional[str] = None
    word_choices: Optional[str] = None  # comma-separated


class ExerciseUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[ExerciseType] = None
    part1: Optional[str] = None
    part2: Optional[str] = None
    prompt: Optional[str] = None
    correct_answer: Optional[str] = None
    translation: Optional[str] = None
    word_choices: Optional[str] = None


class ExerciseOut(BaseModel):
    id: int
    title: str
    type: ExerciseType
    part1: Optional[str]
    part2: Optional[str]
    prompt: str
    correct_answer: str
    translation: Optional[str]
    word_choices: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ExercisePracticeOut(BaseModel):
    """Student view — no correct_answer."""
    id: int
    title: str
    type: ExerciseType
    part1: Optional[str]
    part2: Optional[str]
    prompt: str
    translation: Optional[str]
    word_choices: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ExerciseAnswerSubmit(BaseModel):
    answer: str


class ExerciseAnswerResult(BaseModel):
    correct: bool
    correct_answer: str
    transcribed_text: Optional[str] = None
    reason: Optional[str] = None


class ExerciseSubmissionOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    exercise_id: int
    exercise_title: str
    exercise_prompt: str
    answer: str
    is_correct: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ExerciseSubmissionItemOut(BaseModel):
    exercise_title: str
    exercise_type: str
    exercise_prompt: str
    answer: str
    is_correct: bool
    created_at: datetime


class ExerciseProgressItemOut(BaseModel):
    """Status de revisão espaçada de um exercício para um aluno específico."""
    exercise_id: int
    title: str
    exercise_type: str
    prompt: str
    correct_streak: int
    last_answer: Optional[str] = None
    last_reviewed: Optional[datetime] = None
    next_review: Optional[datetime] = None
    is_due: bool

    class Config:
        from_attributes = True


class ExerciseSubmissionDayOut(BaseModel):
    student_id: int
    student_name: str
    date: str
    submissions: list[ExerciseSubmissionItemOut]
    total: int
    correct_count: int


class ExerciseSubmissionDismissPayload(BaseModel):
    student_id: int
    date: str  # chave no formato YYYY-MM-DD (fuso Brasil), igual ao campo "date" retornado em ExerciseSubmissionDayOut


# ---------- Assignments ----------

class ExerciseAssignPayload(BaseModel):
    exercise_ids: List[int]
    student_id: Optional[int] = None       # mantido por compatibilidade (single)
    student_ids: Optional[List[int]] = None  # novo: múltiplos alunos


class ExerciseAssignmentOut(BaseModel):
    id: int
    exercise_id: int
    student_id: int
    assigned_at: datetime
    exercise: ExercisePracticeOut

    class Config:
        from_attributes = True


# ---------- Histórico de lotes de exercícios ----------

class ExerciseBatchStudentOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class ExerciseBatchExerciseOut(BaseModel):
    id: int
    title: str
    type: str
    part1: Optional[str] = None
    part2: Optional[str] = None
    prompt: str
    correct_answer: str
    translation: Optional[str] = None
    word_choices: Optional[str] = None

    class Config:
        from_attributes = True


class ExerciseBatchOut(BaseModel):
    batch_id: int
    batch_name: str
    sent_at: datetime
    students: List[ExerciseBatchStudentOut]
    exercises: List[ExerciseBatchExerciseOut]

    class Config:
        from_attributes = True


class ExerciseBatchRenamePayload(BaseModel):
    name: str


class ExerciseBatchResendPayload(BaseModel):
    student_ids: List[int]


# ---------- QA ----------

class QAQuestionBulkCreate(BaseModel):
    questions_text: str = Field(description="Uma pergunta por linha")


class QAQuestionOut(BaseModel):
    id: int
    question: str
    created_at: datetime

    class Config:
        from_attributes = True


class QARandomQuestionOut(BaseModel):
    question_id: int
    question: str


class QAAnswerSave(BaseModel):
    student_id: Optional[int] = None
    question_id: Optional[int] = None
    question_text: str
    student_answer: str
    translation: Optional[str] = None


class QAAnswerLogOut(BaseModel):
    id: int
    student_id: int
    question_text: str
    student_answer: str
    translation: Optional[str]
    flashcard_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
