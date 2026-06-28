"""
Configuração da conexão com o banco de dados (PostgreSQL).
"""
import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Carrega variáveis de um arquivo .env local, se existir (uso em desenvolvimento).
# Em produção (Railway) isso não faz nada — lá a DATABASE_URL já vem das
# Variables do painel, e load_dotenv() simplesmente não encontra nenhum
# arquivo .env pra carregar.
load_dotenv()

logger = logging.getLogger(__name__)

# URL do PostgreSQL. Em produção (Railway/Render) defina a variável de
# ambiente DATABASE_URL — a maioria dos provedores já injeta isso
# automaticamente quando você anexa um banco Postgres ao serviço.
# O valor abaixo é só um fallback pra rodar localmente.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/lit_english",
)

# Railway/Heroku às vezes entregam a URL com o esquema antigo "postgres://",
# que o SQLAlchemy 2.x não aceita mais — precisa ser "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SQLALCHEMY_DATABASE_URL = DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # evita erro de conexão "morta" após período de inatividade
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency do FastAPI: abre uma sessão e garante que ela é fechada depois."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _table_exists(conn, table_name: str) -> bool:
    return inspect(conn).has_table(table_name)


def _col_exists(conn, table_name: str, col_name: str) -> bool:
    cols = [c["name"] for c in inspect(conn).get_columns(table_name)]
    return col_name in cols


# ── Correção de FKs sem ON DELETE (migração de SQLite -> Postgres) ──────────
# No SQLite (usado até a v17) as foreign keys não eram validadas por padrão,
# então excluir um aluno/flashcard/exercício "funcionava" mesmo deixando
# linhas órfãs em outras tabelas. No Postgres essas constraints SÃO
# validadas, então qualquer exclusão que deixaria uma linha órfã agora dá
# erro "violates foreign key constraint" (foi o que aconteceu ao tentar
# excluir um aluno: text_assignments ainda referenciava o id dele).
#
# A correção definitiva é fazer as próprias constraints do banco saberem o
# que fazer quando a linha "pai" é excluída (CASCADE = excluir também,
# SET NULL = manter o histórico mas desvincular). Isso já está declarado em
# models.py (ondelete=...) para bancos novos; a lista abaixo conserta as
# constraints que já existem em bancos de produção antigos, sem apagar
# nenhum dado.
_FK_ONDELETE_FIXES = [
    # (tabela, coluna, tabela_referenciada, coluna_referenciada, ação)
    ("flashcard_assignments", "flashcard_id", "flashcards", "id", "CASCADE"),
    ("flashcard_assignments", "student_id", "users", "id", "CASCADE"),
    ("card_progress", "student_id", "users", "id", "CASCADE"),
    ("card_progress", "flashcard_id", "flashcards", "id", "CASCADE"),
    ("review_logs", "student_id", "users", "id", "CASCADE"),
    ("review_logs", "flashcard_id", "flashcards", "id", "CASCADE"),
    ("text_assignments", "text_id", "reading_texts", "id", "CASCADE"),
    ("text_assignments", "student_id", "users", "id", "CASCADE"),
    ("exercise_batch_items", "batch_id", "exercise_batches", "id", "CASCADE"),
    ("exercise_batch_items", "exercise_id", "exercises", "id", "CASCADE"),
    ("exercise_batch_students", "batch_id", "exercise_batches", "id", "CASCADE"),
    ("exercise_batch_students", "student_id", "users", "id", "CASCADE"),
    ("exercise_assignments", "exercise_id", "exercises", "id", "CASCADE"),
    ("exercise_assignments", "student_id", "users", "id", "CASCADE"),
    ("exercise_submissions", "student_id", "users", "id", "CASCADE"),
    ("exercise_submissions", "exercise_id", "exercises", "id", "CASCADE"),
    ("qa_answer_logs", "student_id", "users", "id", "CASCADE"),
    ("qa_answer_logs", "question_id", "qa_questions", "id", "SET NULL"),
    ("qa_answer_logs", "flashcard_id", "flashcards", "id", "SET NULL"),
    ("exercise_progress", "student_id", "users", "id", "CASCADE"),
    ("exercise_progress", "exercise_id", "exercises", "id", "CASCADE"),
]


def _fix_fk_ondelete(conn, table, column, ref_table, ref_column, action):
    """Garante que a FK (table.column -> ref_table.ref_column) tenha o ON DELETE
    desejado. Idempotente: se já estiver correta, não faz nada."""
    row = conn.execute(
        text(
            """
            SELECT tc.constraint_name, rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rc
              ON tc.constraint_name = rc.constraint_name
             AND tc.constraint_schema = rc.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name = :table
              AND kcu.column_name = :column
              AND tc.table_schema = 'public'
            """
        ),
        {"table": table, "column": column},
    ).first()

    if row is None:
        # Constraint ainda não existe (tabela nova, criada já com create_all
        # a partir de models.py atualizado) — nada a corrigir.
        return

    constraint_name, current_rule = row
    desired_rule = "SET NULL" if action == "SET NULL" else "CASCADE"
    if (current_rule or "").upper() == desired_rule:
        return  # já está certo

    conn.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT "{constraint_name}"'))
    conn.execute(
        text(
            f'ALTER TABLE {table} ADD CONSTRAINT "{constraint_name}" '
            f"FOREIGN KEY ({column}) REFERENCES {ref_table}({ref_column}) "
            f"ON DELETE {action}"
        )
    )
    logger.info(
        "Constraint %s (%s.%s) atualizada para ON DELETE %s.", constraint_name, table, column, action
    )


def run_migrations():
    """
    Migrações incrementais e seguras (não apagam dados), portáveis entre bancos.

    Histórico: até a v17 este projeto usava SQLite e essa função tinha uma
    pilha de migrações manuais (PRAGMA table_info, sqlite_master, etc.) para
    ir adicionando colunas/tabelas em bancos antigos sem perder dados.

    A partir da v18 o banco é PostgreSQL e começamos do zero — todas as
    colunas que antes eram adicionadas aqui já estão direto em models.py,
    então o Base.metadata.create_all() (chamado antes desta função, no
    main.py) já cria o schema completo. Esta função fica como ela estava
    nesse projeto: o lugar certo para futuras migrações incrementais
    (ex.: "adicionar coluna X que não existia antes"), usando os helpers
    _table_exists / _col_exists acima, que agora funcionam em qualquer
    banco suportado pelo SQLAlchemy (não só SQLite).

    Exemplo de como adicionar uma migração nova no futuro:

        with engine.connect() as conn:
            if _table_exists(conn, "minha_tabela"):
                if not _col_exists(conn, "minha_tabela", "minha_coluna"):
                    conn.execute(text("ALTER TABLE minha_tabela ADD COLUMN minha_coluna INTEGER DEFAULT 0"))
                    conn.commit()
    """
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            for table, column, ref_table, ref_column, action in _FK_ONDELETE_FIXES:
                try:
                    if _table_exists(conn, table):
                        _fix_fk_ondelete(conn, table, column, ref_table, ref_column, action)
                except Exception:
                    logger.exception(
                        "Falha ao corrigir ON DELETE de %s.%s -> %s.%s (ignorando, sem impacto nos dados).",
                        table, column, ref_table, ref_column,
                    )
                    conn.rollback()
                    continue
            conn.commit()

    logger.info("run_migrations() concluído com sucesso (nenhuma migração pendente).")
