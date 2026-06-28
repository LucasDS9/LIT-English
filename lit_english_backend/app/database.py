"""
Configuração da conexão com o banco de dados (SQLite).
"""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

# Arquivo do banco SQLite (vai ser criado na raiz do projeto)
SQLALCHEMY_DATABASE_URL = "sqlite:///./lit_english.db"

# check_same_thread=False é necessário só pro SQLite + FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
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
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table_name},
    ).fetchone()
    return result is not None


def _col_exists(conn, table_name: str, col_name: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == col_name for row in rows)


def run_migrations():
    """
    Migrações seguras que rodam automaticamente na inicialização (Opção 2 Railway).
    Garante que todas as tabelas e colunas necessárias existam sem apagar dados.
    """
    with engine.connect() as conn:

        # ── 1. exercise_assignments.next_available ─────────────────────────
        if _table_exists(conn, "exercise_assignments"):
            if not _col_exists(conn, "exercise_assignments", "next_available"):
                logger.info("Migração: adicionando exercise_assignments.next_available")
                conn.execute(
                    text("ALTER TABLE exercise_assignments ADD COLUMN next_available DATETIME")
                )
                conn.commit()

        # ── 2. qa_questions.queue_position ────────────────────────────────
        if _table_exists(conn, "qa_questions"):
            if not _col_exists(conn, "qa_questions", "queue_position"):
                logger.info("Migração: adicionando qa_questions.queue_position")
                conn.execute(
                    text(
                        "ALTER TABLE qa_questions ADD COLUMN queue_position INTEGER NOT NULL DEFAULT 0"
                    )
                )
                conn.commit()
                # Backfill: usa a ordem de criação como posição inicial.
                rows = conn.execute(
                    text("SELECT id FROM qa_questions ORDER BY created_at ASC, id ASC")
                ).fetchall()
                for position, row in enumerate(rows):
                    conn.execute(
                        text("UPDATE qa_questions SET queue_position = :pos WHERE id = :qid"),
                        {"pos": position, "qid": row[0]},
                    )
                conn.commit()

        # ── 3. reading_texts.translation — garantir nullable ───────────────
        if _table_exists(conn, "reading_texts"):
            rt_info = conn.execute(text("PRAGMA table_info(reading_texts)")).fetchall()
            translation_col = next((r for r in rt_info if r[1] == "translation"), None)
            if translation_col is not None and translation_col[3] == 1:  # notnull==1
                logger.info("Migração: corrigindo reading_texts.translation nullable")
                conn.execute(text("ALTER TABLE reading_texts RENAME TO reading_texts_old"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE reading_texts (
                            id INTEGER NOT NULL PRIMARY KEY,
                            title VARCHAR NOT NULL,
                            level VARCHAR(2) NOT NULL,
                            content TEXT NOT NULL,
                            translation TEXT,
                            created_at DATETIME
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO reading_texts (id, title, level, content, translation, created_at)
                        SELECT id, title, level, content, translation, created_at FROM reading_texts_old
                        """
                    )
                )
                conn.execute(text("DROP TABLE reading_texts_old"))
                conn.commit()

        # ── 4. card_progress — colunas SM-2 ───────────────────────────────
        if _table_exists(conn, "card_progress"):
            cp_additions = {
                "repetitions": "INTEGER NOT NULL DEFAULT 0",
                "interval_days": "INTEGER NOT NULL DEFAULT 0",
                "ease_factor": "FLOAT NOT NULL DEFAULT 2.5",
                "next_review": "DATETIME",
                "last_reviewed": "DATETIME",
            }
            for col, ddl in cp_additions.items():
                if not _col_exists(conn, "card_progress", col):
                    logger.info("Migração: adicionando card_progress.%s", col)
                    conn.execute(text(f"ALTER TABLE card_progress ADD COLUMN {col} {ddl}"))
            conn.commit()
            # Preenche nulos
            conn.execute(text("UPDATE card_progress SET repetitions  = 0   WHERE repetitions  IS NULL"))
            conn.execute(text("UPDATE card_progress SET interval_days = 0   WHERE interval_days IS NULL"))
            conn.execute(text("UPDATE card_progress SET ease_factor   = 2.5 WHERE ease_factor   IS NULL"))
            conn.execute(
                text("UPDATE card_progress SET next_review = CURRENT_TIMESTAMP WHERE next_review IS NULL")
            )
            conn.commit()

        # ── 5. exercise_progress — colunas de revisão espaçada ────────────
        if _table_exists(conn, "exercise_progress"):
            ep_additions = {
                "correct_streak": "INTEGER DEFAULT 0",
                "next_review": "DATETIME",
                "last_reviewed": "DATETIME",
            }
            for col, ddl in ep_additions.items():
                if not _col_exists(conn, "exercise_progress", col):
                    logger.info("Migração: adicionando exercise_progress.%s", col)
                    conn.execute(text(f"ALTER TABLE exercise_progress ADD COLUMN {col} {ddl}"))
            conn.commit()
            conn.execute(
                text("UPDATE exercise_progress SET correct_streak = 0 WHERE correct_streak IS NULL")
            )
            conn.execute(
                text(
                    "UPDATE exercise_progress SET next_review = CURRENT_TIMESTAMP WHERE next_review IS NULL"
                )
            )
            conn.commit()

        # ── 6. Tabelas de lotes de exercícios (novas na V18) ──────────────
        # O create_all() já cria estas tabelas se não existirem, mas garantimos
        # aqui de forma explícita para máxima segurança no Railway.

        if not _table_exists(conn, "exercise_batches"):
            logger.info("Migração: criando tabela exercise_batches")
            conn.execute(
                text(
                    """
                    CREATE TABLE exercise_batches (
                        id INTEGER NOT NULL PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        sent_at DATETIME
                    )
                    """
                )
            )
            conn.commit()

        if not _table_exists(conn, "exercise_batch_items"):
            logger.info("Migração: criando tabela exercise_batch_items")
            conn.execute(
                text(
                    """
                    CREATE TABLE exercise_batch_items (
                        id INTEGER NOT NULL PRIMARY KEY,
                        batch_id INTEGER NOT NULL REFERENCES exercise_batches(id),
                        exercise_id INTEGER NOT NULL REFERENCES exercises(id)
                    )
                    """
                )
            )
            conn.commit()

        if not _table_exists(conn, "exercise_batch_students"):
            logger.info("Migração: criando tabela exercise_batch_students")
            conn.execute(
                text(
                    """
                    CREATE TABLE exercise_batch_students (
                        id INTEGER NOT NULL PRIMARY KEY,
                        batch_id INTEGER NOT NULL REFERENCES exercise_batches(id),
                        student_id INTEGER NOT NULL REFERENCES users(id)
                    )
                    """
                )
            )
            conn.commit()

        # ── 7. exercise_submissions.dismissed_by_professor (novo na V18) ──
        if _table_exists(conn, "exercise_submissions"):
            if not _col_exists(conn, "exercise_submissions", "dismissed_by_professor"):
                logger.info("Migração: adicionando exercise_submissions.dismissed_by_professor")
                conn.execute(
                    text(
                        "ALTER TABLE exercise_submissions ADD COLUMN dismissed_by_professor BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
                conn.commit()

        logger.info("run_migrations() concluído com sucesso.")
