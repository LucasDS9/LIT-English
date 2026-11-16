"""
Narração dos textos padrão (Read and Listen) com ElevenLabs.

- Chave: variável de ambiente LIT_narrator (secret no Railway).
- Voz: ELEVENLABS_VOICE_ID (padrão abaixo). Modelo: ELEVENLABS_MODEL_ID
  (padrão: eleven_v4_turbo).
- Cada trecho é gerado uma única vez e guardado no banco (NarrationAudio):
  a partir daí todos os alunos recebem do banco, sem custo e sem nova chamada.
- No startup, os textos padrão são pré-gerados em segundo plano, então o
  primeiro aluno já encontra tudo pronto.
"""
import asyncio
import hashlib
import logging
import os
import re

import httpx
from sqlalchemy.orm import Session

from app.models import NarrationAudio

logger = logging.getLogger(__name__)

DEFAULT_VOICE_ID = "1s5ETcPtsJ9W2cUUQrDb"
DEFAULT_MODEL_ID = "eleven_v4_turbo"
ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

_LANGUAGE_CODES = {"ingles": "en", "italiano": "it", "frances": "fr", "mandarim": "zh"}

# Mesmo limite do front (TTS_CHUNK_MAX em textos.js).
CHUNK_MAX = 180


def api_key() -> str | None:
    return (os.environ.get("LIT_narrator") or os.environ.get("LIT_NARRATOR") or "").strip() or None


def voice_id() -> str:
    return (os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID).strip()


def model_id() -> str:
    return (os.environ.get("ELEVENLABS_MODEL_ID") or DEFAULT_MODEL_ID).strip()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def split_into_chunks(text: str) -> list[str]:
    """Port de splitIntoChunks (textos.js) — os trechos pré-gerados batem com os do front."""
    normalized = normalize(text)
    if not normalized:
        return []
    sentences = re.findall(r"[^.!?。！？]+[.!?。！？]*\s*", normalized) or [normalized]
    chunks: list[str] = []
    for sentence in sentences:
        trimmed = sentence.strip()
        if not trimmed:
            continue
        if len(trimmed) <= CHUNK_MAX:
            chunks.append(trimmed)
            continue
        current = ""
        for word in trimmed.split(" "):
            candidate = f"{current} {word}" if current else word
            if len(candidate) > CHUNK_MAX and current:
                chunks.append(current)
                current = word
            else:
                current = candidate
        if current:
            chunks.append(current)
    return chunks


def cache_key(language: str, text: str) -> str:
    raw = f"{voice_id()}|{model_id()}|{language}|{normalize(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _generate(language: str, text: str) -> bytes:
    key = api_key()
    if not key:
        raise RuntimeError("LIT_narrator não configurada.")
    body = {"text": text, "model_id": model_id()}
    code = _LANGUAGE_CODES.get(language)
    if code:
        body["language_code"] = code
    async with httpx.AsyncClient(timeout=40.0) as client:
        resp = await client.post(
            ELEVENLABS_URL.format(voice_id=voice_id()),
            params={"output_format": "mp3_44100_64"},
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            json=body,
        )
    if resp.status_code != 200 or not resp.content:
        raise RuntimeError(f"ElevenLabs {resp.status_code}: {resp.text[:200]}")
    return resp.content


async def get_narration(db: Session, language: str, text: str) -> bytes:
    """Devolve o áudio do banco; só chama a ElevenLabs se ainda não existir."""
    text = normalize(text)
    k = cache_key(language, text)
    row = db.query(NarrationAudio).filter(NarrationAudio.cache_key == k).first()
    if row:
        return bytes(row.audio)
    audio = await _generate(language, text)
    try:
        db.add(NarrationAudio(cache_key=k, language=language, audio=audio))
        db.commit()
    except Exception:  # corrida: outro request gravou primeiro
        db.rollback()
    return audio


async def prewarm_default_texts(session_factory) -> None:
    """Pré-gera, em segundo plano, a narração dos textos padrão que ainda faltam."""
    if not api_key():
        logger.info("LIT_narrator ausente: pré-geração da narração ignorada.")
        return
    from app.default_texts import DEFAULT_TEXTS

    for language, data in DEFAULT_TEXTS.items():
        for chunk in split_into_chunks(data["content"]):
            try:
                with session_factory() as db:
                    await get_narration(db, language, chunk)
            except Exception as exc:
                logger.warning("Pré-geração da narração falhou (%s): %s", language, exc)
                await asyncio.sleep(1)
    logger.info("Narração dos textos padrão pronta.")
