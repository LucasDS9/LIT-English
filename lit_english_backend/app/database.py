"""
Configuração da conexão com o banco de dados (SQLite).
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

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


def run_migrations():
    """Migrações leves para SQLite (colunas adicionadas após o deploy inicial)."""
    with engine.connect() as conn:
        cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(exercise_assignments)")).fetchall()
        }
        if "next_available" not in cols:
            conn.execute(
                text("ALTER TABLE exercise_assignments ADD COLUMN next_available DATETIME")
            )
            conn.commit()

        qa_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(qa_questions)")).fetchall()
        }
        if "queue_position" not in qa_cols:
            conn.execute(
                text("ALTER TABLE qa_questions ADD COLUMN queue_position INTEGER NOT NULL DEFAULT 0")
            )
            conn.commit()
            # Backfill: usa a ordem de criação como posição inicial na fila.
            rows = conn.execute(
                text("SELECT id FROM qa_questions ORDER BY created_at ASC, id ASC")
            ).fetchall()
            for position, row in enumerate(rows):
                conn.execute(
                    text("UPDATE qa_questions SET queue_position = :pos WHERE id = :qid"),
                    {"pos": position, "qid": row[0]},
                )
            conn.commit()

        # reading_texts.translation precisa ser opcional (o frontend já trata
        # como campo opcional, mas a tabela antiga foi criada com NOT NULL).
        rt_info = conn.execute(text("PRAGMA table_info(reading_texts)")).fetchall()
        translation_col = next((row for row in rt_info if row[1] == "translation"), None)
        if translation_col is not None and translation_col[3] == 1:  # notnull == 1
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

        # card_progress: bancos antigos (de versões anteriores ao SM-2 atual)
        # podem não ter algumas colunas, ou ter ficado com colunas nulas.
        cp_info = conn.execute(text("PRAGMA table_info(card_progress)")).fetchall()
        if cp_info:
            cp_cols = {row[1] for row in cp_info}
            cp_additions = {
                "repetitions": "INTEGER NOT NULL DEFAULT 0",
                "interval_days": "INTEGER NOT NULL DEFAULT 0",
                "ease_factor": "FLOAT NOT NULL DEFAULT 2.5",
                "next_review": "DATETIME",
                "last_reviewed": "DATETIME",
            }
            for col, ddl in cp_additions.items():
                if col not in cp_cols:
                    conn.execute(text(f"ALTER TABLE card_progress ADD COLUMN {col} {ddl}"))
            conn.commit()
            # Preenche valores nulos que possam ter sobrado de colunas antigas.
            conn.execute(text("UPDATE card_progress SET repetitions = 0 WHERE repetitions IS NULL"))
            conn.execute(text("UPDATE card_progress SET interval_days = 0 WHERE interval_days IS NULL"))
            conn.execute(text("UPDATE card_progress SET ease_factor = 2.5 WHERE ease_factor IS NULL"))
            conn.execute(
                text("UPDATE card_progress SET next_review = CURRENT_TIMESTAMP WHERE next_review IS NULL")
            )
            conn.commit()

        # exercise_progress: idem, garante colunas e preenche nulos (evita
        # erro ao incrementar correct_streak quando ele vem None do banco).
        ep_info = conn.execute(text("PRAGMA table_info(exercise_progress)")).fetchall()
        if ep_info:
            ep_cols = {row[1] for row in ep_info}
            ep_additions = {
                "correct_streak": "INTEGER DEFAULT 0",
                "next_review": "DATETIME",
                "last_reviewed": "DATETIME",
            }
            for col, ddl in ep_additions.items():
                if col not in ep_cols:
                    conn.execute(text(f"ALTER TABLE exercise_progress ADD COLUMN {col} {ddl}"))
            conn.commit()
            conn.execute(
                text("UPDATE exercise_progress SET correct_streak = 0 WHERE correct_streak IS NULL")
            )
            conn.execute(
                text("UPDATE exercise_progress SET next_review = CURRENT_TIMESTAMP WHERE next_review IS NULL")
            )
            conn.commit()
