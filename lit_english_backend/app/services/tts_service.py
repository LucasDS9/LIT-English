"""
TTS "sob demanda" (fora da sessão de tempo real), usado pelo botão "Ouvir"
de cada bolha de mensagem no chat -- inclusive para tocar a tradução em
português quando o aluno clica em "Traduzir".

Usa o endpoint REST clássico do Azure Speech (não a Voice Live), reutilizando
as mesmas AZURE_SPEECH_KEY / AZURE_SPEECH_REGION.
"""

from __future__ import annotations

import logging
import xml.sax.saxutils as saxutils

import httpx

from . import voice_config as cfg

logger = logging.getLogger("lit.tts")


def _voice_for_lang(lang: str) -> str:
    if lang.startswith("pt"):
        return "pt-BR-FranciscaNeural"
    return cfg.DEFAULT_TUTOR_VOICE


def _ssml(text: str, voice: str, lang: str) -> str:
    safe_text = saxutils.escape(text)
    return (
        f'<speak version="1.0" xml:lang="{lang}">'
        f'<voice name="{voice}">{safe_text}</voice>'
        f"</speak>"
    )


async def synthesize_speech(text: str, lang: str = "en-US") -> bytes:
    """Retorna áudio MP3 (bytes) pronto para stream ao frontend."""
    cfg.require_configured()
    if not cfg.TTS_REST_URL:
        raise RuntimeError("AZURE_SPEECH_REGION não configurada -- TTS indisponível.")

    voice = _voice_for_lang(lang)
    ssml = _ssml(text, voice, lang)

    headers = {
        "Ocp-Apim-Subscription-Key": cfg.AZURE_SPEECH_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "lit-english-backend",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(cfg.TTS_REST_URL, content=ssml.encode("utf-8"), headers=headers)
        if resp.status_code != 200:
            logger.error("Falha no TTS Azure: %s - %s", resp.status_code, resp.text[:300])
            resp.raise_for_status()
        return resp.content
