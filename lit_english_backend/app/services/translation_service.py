"""
Tradução das falas do tutor (EN) para português, para o botão "Traduzir".

Usa a Groq (mesma IA de texto usada na análise gramatical da Conversa com IA
Tutor -- ver conversation_ai.py), em vez da sessão de voz em tempo real da
Azure: assim a tradução não fica dependendo de credenciais/estado do módulo
de voz, e usa o mesmo padrão confiável (JSON mode) já usado no resto da
plataforma.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("lit.translation")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

_SYSTEM_PROMPT = (
    "Você traduz frases curtas de inglês para português do Brasil, de forma "
    "natural e coloquial, como uma pessoa falaria. Responda APENAS com um "
    'JSON no formato exato: {"translated": "..."}, sem nenhum texto antes ou '
    "depois, sem repetir o texto original dentro da tradução."
)


async def translate_to_pt_br(text: str) -> str:
    text = text.strip()
    if not text:
        return ""

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY não configurada -- tradução indisponível.")
        return text

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
    }

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            translated = str(parsed.get("translated", "")).strip()
            return translated or text
    except Exception as exc:
        logger.warning("Falha ao traduzir via Groq: %s", exc)
        return text
