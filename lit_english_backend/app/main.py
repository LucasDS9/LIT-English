"""
Ponto de entrada da aplicação FastAPI — v18.
Startup: cria tabelas + roda migrações automáticas (Railway / Railway-like).
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, run_migrations
from app.routers import admin, auth, dashboard, exercises, flashcards, qa, texts, tts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Cria tabelas que ainda não existem (seguro: não apaga dados)
logger.info("Inicializando banco de dados...")
Base.metadata.create_all(bind=engine)

# 2. Migrações incrementais (adiciona colunas / tabelas novas com segurança)
logger.info("Rodando migrações...")
run_migrations()
logger.info("Banco de dados pronto.")

app = FastAPI(title="LIT English API", version="0.18.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(flashcards.router)
app.include_router(texts.router)
app.include_router(exercises.router)
app.include_router(qa.router)
app.include_router(tts.router)
app.include_router(dashboard.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "LIT English API v18 está no ar 🚀"}
