"""
Schemas Pydantic.
"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.models import (
    AccessType,
    ExerciseType,
    ReadingLevel,
    ReviewCardStatus,
    ReviewMode,
    UserRole,
    VocabWordStatus,
)

# Línguas-alvo aceitas hoje no cadastro de Acesso Especial. Só existe estrutura
# (campo salvo no usuário, TTS e conteúdo de Home) — ainda sem o vocabulário/
# flashcards (frases) montado para "frances" e "ingles" nesse contexto.
# Pra liberar uma nova língua no futuro, basta adicionar aqui.
ALLOWED_TARGET_LANGUAGES = {"ingles", "italiano", "frances"}


# ---------- Auth ----------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    whatsapp: Optional[str] = None
    password: str
    role: UserRole = UserRole.aluno
    access_type: AccessType = AccessType.padrao
    native_language: Optional[str] = None
    target_language: Optional[str] = None


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
    access_type: AccessType
    native_language: Optional[str] = None
    target_language: Optional[str] = None
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


class FlashcardSelfAdd(BaseModel):
    """
    Aluno salvando um flashcard próprio — seja pelo popup de vocabulário
    (Read and Listen, front+back sempre preenchidos) seja pelo botão
    "Adicionar flashcard" da tela de Flashcards, onde `back` é opcional:
    se vier vazio, o backend gera a tradução automaticamente.
    """
    front: str
    back: Optional[str] = None


# ---------- Revisão ----------

class ReviewCardOut(BaseModel):
    flashcard_id: int
    front: str
    back: str
    status: Optional[ReviewCardStatus] = None
    mode: ReviewMode = ReviewMode.flip
    explanation: Optional[str] = None


class ReviewQueueOut(BaseModel):
    cards: list[ReviewCardOut]
    remaining_in_window: int
    limit_per_window: int
    blocked_by: Optional[str] = None
    blocked_message: Optional[str] = None


class ReviewSubmit(BaseModel):
    quality: Optional[int] = Field(default=None, ge=0, le=5)
    typed_answer: Optional[str] = None


class ReviewResultOut(BaseModel):
    """Resposta após revisão (flip ou digitação)."""
    correct: bool
    correct_answer: Optional[str] = None
    review_status: Optional[ReviewCardStatus] = None
    review_mode: ReviewMode = ReviewMode.flip
    reason: Optional[str] = None
    confidence: Optional[float] = None
    transcribed_text: Optional[str] = None


class WordPronunciationScore(BaseModel):
    """Pontuação por palavra — Azure Pronunciation Assessment."""
    word: str
    score: int = Field(ge=0, le=100)
    error_type: Optional[str] = None


class FlashcardPronunciationResult(BaseModel):
    """Feedback de pronúncia opcional em flashcards (não afeta SM-2)."""
    correct: bool
    correct_answer: str
    transcribed_text: Optional[str] = None
    reason: Optional[str] = None
    feedback_title: Optional[str] = None
    score: Optional[int] = Field(default=None, ge=0, le=100)
    word_scores: Optional[List[WordPronunciationScore]] = None


class CardProgressOut(BaseModel):
    flashcard_id: int
    repetitions: int
    interval_days: int
    ease_factor: float
    next_review: datetime
    review_status: Optional[ReviewCardStatus] = None
    review_mode: ReviewMode = ReviewMode.flip
    correct_streak: int = 0

    class Config:
        from_attributes = True


class VocabularyItemOut(BaseModel):
    """Vocabulário de um aluno específico: flashcard + status de revisão."""
    flashcard_id: int
    front: str
    back: str
    next_review: Optional[datetime] = None
    is_due: bool
    review_status: Optional[ReviewCardStatus] = None
    review_mode: Optional[ReviewMode] = None


class FlashcardResendPayload(BaseModel):
    """Reenvia (atribui) um ou mais flashcards já existentes a outro(s) aluno(s)."""
    flashcard_ids: List[int] = Field(min_length=1)
    student_ids: List[int] = Field(min_length=1)


# ---------- Histórico de lotes de flashcards ----------

class FlashcardBatchCardIn(BaseModel):
    front: str
    back: str


class FlashcardBatchCreatePayload(BaseModel):
    """Cria vários flashcards de uma vez, agrupados num lote (deck) nomeado,
    e já envia para os alunos selecionados."""
    name: str
    cards: List[FlashcardBatchCardIn] = Field(min_length=1)
    student_ids: List[int] = Field(min_length=1)


class FlashcardBatchStudentOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class FlashcardBatchCardOut(BaseModel):
    id: int
    front: str
    back: str

    class Config:
        from_attributes = True


class FlashcardBatchOut(BaseModel):
    batch_id: int
    batch_name: str
    sent_at: datetime
    students: List[FlashcardBatchStudentOut]
    cards: List[FlashcardBatchCardOut]

    class Config:
        from_attributes = True


class FlashcardBatchRenamePayload(BaseModel):
    name: str


class FlashcardBatchResendPayload(BaseModel):
    student_ids: List[int] = Field(min_length=1)


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


class WordLookupRequest(BaseModel):
    """Payload enviado quando o aluno clica numa palavra dentro de um texto."""
    word: str
    sentence: str
    text_id: Optional[int] = None


class WordLookupOut(BaseModel):
    """Conteúdo do popup de vocabulário: tradução contextual + frase de exemplo."""
    word: str
    translation: str
    example_en: str
    example_pt: str


# ---------- Aprender (treino de vocabulário por múltipla escolha) ----------

class VocabWordCreate(BaseModel):
    word: str
    part_of_speech: str
    translation: str
    # Ao menos um dos dois precisa vir preenchido: `example_sentence` (a
    # maioria das palavras) ou `tip` (ex.: saudações, sem frase de exemplo).
    example_sentence: Optional[str] = None
    tip: Optional[str] = None
    # Sempre exatamente 3 opções erradas — junto com `translation` formam as
    # 4 opções fixas mostradas ao aluno.
    distractors: List[str] = Field(min_length=3, max_length=3)
    # Explicação curta, mostrada no verso do card só depois que o aluno
    # responde (junto com a resposta certa) — nunca antes.
    explanation: Optional[str] = None
    # Língua-alvo da palavra ("ingles" por padrão, hoje o único conteúdo
    # existente). Determina pra quem ela fica "nativa" — ver student_ids.
    language: str = "ingles"
    # Se omitido (ou vazio), a palavra é atribuída automaticamente a TODOS
    # os alunos aprovados no momento cuja língua bate com `language` — e
    # também a qualquer aluno aprovado depois (ver approve_student em
    # admin.py), ficando nativa pra tela Aprender de todos os alunos
    # daquela língua, sem precisar selecionar aluno por aluno.
    student_ids: Optional[List[int]] = None


class VocabWordUpdate(BaseModel):
    word: Optional[str] = None
    part_of_speech: Optional[str] = None
    translation: Optional[str] = None
    example_sentence: Optional[str] = None
    tip: Optional[str] = None
    distractors: Optional[List[str]] = Field(default=None, min_length=3, max_length=3)
    explanation: Optional[str] = None
    language: Optional[str] = None
    student_ids: Optional[List[int]] = None


class VocabWordOut(BaseModel):
    id: int
    word: str
    part_of_speech: str
    translation: str
    example_sentence: Optional[str] = None
    tip: Optional[str] = None
    distractors: List[str]
    explanation: Optional[str] = None
    language: str
    created_at: datetime
    students: List[FlashcardStudentOut] = []


class VocabLearnCardOut(BaseModel):
    """Card mostrado na tela Aprender. NÃO inclui `translation` (a resposta
    certa) e as 4 `options` vêm embaralhadas — o aluno não tem como saber
    qual é a certa antes de responder. A tradução da própria palavra também
    não aparece em nenhum outro campo (ex.: se o aluno clicar nela na frase
    de exemplo, o frontend não deve chamar o lookup contextual pra ela)."""
    word_id: int
    word: str
    part_of_speech: str
    example_sentence: Optional[str] = None
    tip: Optional[str] = None
    options: List[str]  # sempre 4, em ordem embaralhada


class VocabLearnQueueOut(BaseModel):
    cards: List[VocabLearnCardOut]
    total_assigned: int
    total_learned: int
    new_words_count: int = 0


class VocabLearnSubmit(BaseModel):
    selected_option: str = Field(min_length=1)


class VocabLearnResult(BaseModel):
    """Resultado devolvido depois que o aluno responde — é só aqui que a
    resposta certa e a explicação podem aparecer, pra virar o verso do
    card (nunca antes, em VocabLearnCardOut)."""
    correct: bool
    correct_answer: str
    explanation: Optional[str] = None
    graduated_to_review: bool = False


class VocabWordProgressOut(BaseModel):
    """Vocabulário (Aprender) de um aluno específico, visão do professor."""
    word_id: int
    word: str
    part_of_speech: str
    translation: str
    status: VocabWordStatus
    next_review: datetime


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


# ---------- Dashboard (tela inicial do aluno) ----------

class DashboardMetricsOut(BaseModel):
    """Métricas consolidadas da tela inicial do aluno."""
    accuracy_rate: int             # Taxa de acerto (%), 0-100
    performance_points: int        # Pontos obtidos (eficiência)
    performance_max: int           # Pontos máximos possíveis (eficiência)
    lit_points: int                # Total de LIT Points
    exercises_today: int           # Exercícios respondidos hoje
    exercises_today_target: int    # Exercícios disponíveis hoje (feitos + pendentes)
    exercises_total: int           # Total de exercícios respondidos desde sempre
    reading_minutes: int           # Minutos totais de Read and Listen
    flashcards_reviewed: int       # Total de flashcards revisados


class StudentDetailsOut(BaseModel):
    """Detalhes de um aluno para o professor (Configurações > Ver detalhes)."""
    student: UserOut
    metrics: DashboardMetricsOut


class ReadingHeartbeatIn(BaseModel):
    """Enviado periodicamente pelo frontend enquanto o aluno tem um texto
    aberto, para contabilizar tempo ativo de estudo (Read and Listen)."""
    seconds: int = Field(ge=1, le=120)


class ReadingHeartbeatOut(BaseModel):
    total_seconds: int
    points_awarded: int


class NextActivityOut(BaseModel):
    """Próxima atividade recomendada para o aluno (fila global)."""
    activity: str  # "exercises" | "flashcards" | "none"
    url: Optional[str] = None
    message: Optional[str] = None

# ---------- Teste de Nivelamento (leads) ----------

class LevelTestQuestionDetail(BaseModel):
    """Detalhe de UMA questão do teste de nivelamento: o que o aluno
    escolheu/digitou, a resposta correta e se acertou. Usado no painel do
    professor (botão "Ver mais" em cada lead)."""
    id: int
    number: Optional[int] = None
    type: Optional[str] = None
    level: Optional[str] = None
    subject: Optional[str] = None
    question_en: Optional[str] = None
    question_pt: Optional[str] = None
    is_correct: bool = False
    student_answer: Optional[Any] = None
    chosen_text: Optional[str] = None
    correct_text: Optional[str] = None
    reference_answer: Optional[str] = None


class LevelTestResultIn(BaseModel):
    """Enviado pelo app do teste (lit_english_teste_ingles) ao final da correção."""
    nome: str
    whatsapp: Optional[str] = ""
    acertos: int = 0
    erros: int = 0
    total_questoes: int = 0
    porcentagem: int = 0
    pontos: int = 0
    pontuacao_maxima: int = 0
    desempenho_a1: int = 0
    desempenho_a2: int = 0
    desempenho_b1: int = 0
    desempenho_b2: int = 0
    nivel_estimado: str = ""
    trilha_recomendada: str = ""
    quer_aula_experimental: bool = False
    quer_analise_plano: bool = False
    respostas_detalhadas: Optional[List[LevelTestQuestionDetail]] = None


class LevelTestWhatsappIn(BaseModel):
    """Enviado quando o aluno deixa o WhatsApp na tela de resultado (depois
    do teste já corrigido)."""
    whatsapp: str
    quer_aula_experimental: bool = False
    quer_analise_plano: bool = False


class LevelTestResultOut(BaseModel):
    id: int
    nome: str
    whatsapp: Optional[str] = ""
    acertos: int
    erros: int
    total_questoes: int
    porcentagem: int
    pontos: int
    pontuacao_maxima: int
    desempenho_a1: int
    desempenho_a2: int
    desempenho_b1: int
    desempenho_b2: int = 0
    nivel_estimado: str
    trilha_recomendada: str
    quer_aula_experimental: bool
    quer_analise_plano: bool
    respostas_detalhadas: Optional[List[LevelTestQuestionDetail]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Leads do site institucional (Comece Agora / Entre em Contato) ----------

class SiteLeadIn(BaseModel):
    """Enviado pela landing page pública (index.html) — tanto pelo modal
    "Agendar Aula Experimental" (source="comece_agora") quanto pelo
    formulário "Entre em Contato" (source="contato")."""
    source: str
    nome: str
    whatsapp: str
    objetivo: Optional[str] = None
    nivel: Optional[str] = None
    mensagem: Optional[str] = None


class SiteLeadOut(BaseModel):
    id: int
    source: str
    nome: str
    whatsapp: str
    objetivo: Optional[str] = None
    nivel: Optional[str] = None
    mensagem: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
