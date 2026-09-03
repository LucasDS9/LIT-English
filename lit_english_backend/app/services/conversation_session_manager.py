"""
Gerencia o histórico das sessões de "Conversa com IA Tutor" por aluno.

Regra pedida: se o aluno ficar 30 minutos sem interagir, todo o histórico
daquela sessão é apagado e, na próxima mensagem, uma sessão nova começa do zero.

Isso é feito em memória (dict + asyncio), por processo. Se a API rodar em mais
de uma instância/worker no Railway, troque o dict por Redis (mesma interface).

Desde a migração para o fluxo "manda áudio -> transcreve -> analisa -> IA
responde" (ver app/routers/conversation.py e app/services/conversation_ai.py),
essa classe não mantém mais nenhuma conexão ao vivo com a Azure -- é só um
histórico de turnos, bem mais simples e sem os problemas de concorrência que
uma conexão WebSocket persistente por aluno tinha.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Optional

from . import voice_config as cfg

logger = logging.getLogger("lit.conversation_sessions")


@dataclass
class ConversationTurn:
    role: str  # "student" | "tutor"
    text: str
    analysis: Optional[dict] = None  # preenchido quando role == "student"
    at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))


@dataclass
class ConversationSession:
    student_id: str
    student_name: str
    level: str | None = None
    target_language: str = "ingles"
    native_language: str = "pt"
    history: list[ConversationTurn] = field(default_factory=list)
    last_activity: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    def touch(self) -> None:
        self.last_activity = dt.datetime.now(dt.timezone.utc)

    def is_expired(self, timeout_minutes: int) -> bool:
        limit = self.last_activity + dt.timedelta(minutes=timeout_minutes)
        return dt.datetime.now(dt.timezone.utc) > limit

    def history_for_ai(self) -> list[dict]:
        """Formato simples [{"role":..., "text":...}] pro conversation_ai.py."""
        return [{"role": t.role, "text": t.text} for t in self.history]


class ConversationSessionManager:
    """Singleton simples (instancie uma vez e reutilize no app todo)."""

    def __init__(self, timeout_minutes: int = cfg.SESSION_TIMEOUT_MINUTES):
        self.timeout_minutes = timeout_minutes
        self._sessions: dict[str, ConversationSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def start_background_cleanup(self) -> None:
        """Chame isso uma vez no startup do FastAPI (evento 'startup')."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Loop de limpeza de sessões de conversa iniciado (timeout=%smin)", self.timeout_minutes)

    async def stop_background_cleanup(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)  # checa a cada 1 minuto
                await self._expire_stale_sessions()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Erro no loop de limpeza de sessões")

    async def _expire_stale_sessions(self) -> None:
        async with self._lock:
            expired_ids = [
                sid for sid, s in self._sessions.items()
                if s.is_expired(self.timeout_minutes)
            ]
            for sid in expired_ids:
                logger.info("Sessão de conversa expirada por inatividade: %s", sid)
                del self._sessions[sid]

    async def get_or_create(
        self,
        student_id: str,
        student_name: str,
        level: str | None = None,
        target_language: str = "ingles",
        native_language: str = "pt",
    ) -> ConversationSession:
        async with self._lock:
            existing = self._sessions.get(student_id)
            if existing and not existing.is_expired(self.timeout_minutes):
                existing.touch()
                if level:
                    existing.level = level
                existing.target_language = target_language or existing.target_language
                existing.native_language = native_language or existing.native_language
                return existing

            session = ConversationSession(
                student_id=student_id,
                student_name=student_name,
                level=level,
                target_language=target_language or "ingles",
                native_language=native_language or "pt",
            )
            self._sessions[student_id] = session
            return session

    async def touch(self, student_id: str) -> None:
        async with self._lock:
            s = self._sessions.get(student_id)
            if s:
                s.touch()

    async def record_turn(self, student_id: str, turn: ConversationTurn) -> None:
        async with self._lock:
            s = self._sessions.get(student_id)
            if s:
                s.history.append(turn)
                s.touch()

    def get(self, student_id: str) -> Optional[ConversationSession]:
        """Leitura simples e síncrona (sem lock) -- ok para os usos de GET/consulta."""
        return self._sessions.get(student_id)

    async def end_session(self, student_id: str) -> None:
        async with self._lock:
            self._sessions.pop(student_id, None)


# Instância única usada pelo router. Importe esta variável.
conversation_sessions = ConversationSessionManager()
