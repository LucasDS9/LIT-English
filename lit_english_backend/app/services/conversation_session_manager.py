"""
Gerencia o ciclo de vida das sessões de "Conversa com IA Tutor" por aluno.

Regra pedida: se o aluno ficar 30 minutos sem interagir, todo o histórico
daquela sessão é apagado e, na próxima mensagem, uma sessão nova começa do zero.

Isso é feito em memória (dict + asyncio), por processo. Se a API rodar em mais
de uma instância/worker no Railway, troque o dict por Redis (mesma interface,
só troca o storage -- ver nota no fim do arquivo).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Optional

from .voice_live_client import VoiceLiveSession
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
    voice_live: VoiceLiveSession
    history: list[ConversationTurn] = field(default_factory=list)
    last_activity: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    # Tarefa asyncio que está atualmente "escutando" os eventos da Azure
    # (voice_live.events()) para ESTA sessão. Um WebSocket da Azure só
    # aguenta UM consumidor por vez -- se o aluno der refresh e uma nova
    # conexão reaproveitar essa sessão antes da tarefa antiga terminar de
    # verdade de cancelar, as duas concorrem pela mesma conexão e o
    # resultado é a IA "parar de responder" (quem descreve o bug tem esse
    # sintoma exato). O router usa esse campo pra esperar a tarefa antiga
    # encerrar antes de criar a nova -- ver conversation_ws() no router.
    active_forwarder_task: Optional["asyncio.Task"] = field(default=None, repr=False, compare=False)

    def touch(self) -> None:
        self.last_activity = dt.datetime.now(dt.timezone.utc)

    def is_expired(self, timeout_minutes: int) -> bool:
        limit = self.last_activity + dt.timedelta(minutes=timeout_minutes)
        return dt.datetime.now(dt.timezone.utc) > limit


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
            await self.end_session(sid)

    async def get_or_create(
        self, student_id: str, student_name: str, voice: str | None = None, level: str | None = None
    ) -> ConversationSession:
        async with self._lock:
            existing = self._sessions.get(student_id)
            if existing and not existing.is_expired(self.timeout_minutes):
                existing.touch()
                return existing
            if existing:
                # sessão expirada -- descarta o histórico e cria uma nova
                await self._close_voice_live(existing)
                del self._sessions[student_id]

        voice_live = VoiceLiveSession(student_name=student_name, voice=voice, level=level)
        await voice_live.connect()
        await voice_live.configure()

        session = ConversationSession(
            student_id=student_id,
            student_name=student_name,
            voice_live=voice_live,
        )
        async with self._lock:
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

    async def end_session(self, student_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(student_id, None)
        if session:
            await self._close_voice_live(session)

    async def _close_voice_live(self, session: ConversationSession) -> None:
        try:
            await session.voice_live.close()
        except Exception:
            logger.exception("Erro ao fechar conexão Voice Live da sessão %s", session.student_id)


# Instância única usada pelo router. Importe esta variável.
conversation_sessions = ConversationSessionManager()


# ---------------------------------------------------------------------------
# Nota sobre múltiplas instâncias (Railway com >1 worker/réplica):
#
# O WebSocket do aluno com o backend, e o WebSocket do backend com a Azure,
# precisam terminar no MESMO processo -- então o dict em memória funciona bem
# desde que o Railway mantenha "sticky" a conexão WS do aluno na mesma réplica
# (é o padrão para WebSockets). Se um dia você escalar horizontalmente e usar
# um load balancer sem sticky sessions para WS, essa classe precisa migrar o
# `_sessions` para um mecanismo que reconecte a sessão à réplica certa -- não
# dá pra simplesmente usar Redis aqui, pois a conexão WebSocket viva com a
# Azure não pode ser serializada. Nesse cenário, o mais simples é fixar 1
# worker para essa rota específica.
# ---------------------------------------------------------------------------
