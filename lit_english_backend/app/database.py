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
    logger.info("run_migrations() concluído com sucesso (nenhuma migração pendente).")
