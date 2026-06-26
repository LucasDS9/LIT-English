"""
Ponto de entrada da aplicação FastAPI.
Etapa 6: autenticação + admin + flashcards + read and listen + exercícios + QA.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, run_migrations
from app.routers import admin, auth, exercises, flashcards, qa, texts, tts

# Cria as tabelas no banco (se ainda não existirem)
Base.metadata.create_all(bind=engine)
run_migrations()

app = FastAPI(title="LIT English API", version="0.1.0")

# Libera o frontend (em dev, qualquer origem; depois restrinja para o domínio real)
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


@app.get("/")
def root():
    return {"status": "ok", "message": "LIT English API está no ar 🚀"}
