"""
Tradução das falas do tutor (EN) para português, para o botão "Traduzir".

Reaproveita o mesmo recurso Azure (phi4-mm-realtime) via uma chamada de texto
pontual -- sem precisar de nenhuma credencial extra (Translator, etc).
"""

from __future__ import annotations

from .voice_live_client import voicelive_text_completion

_SYSTEM_PROMPT = (
    "Você traduz frases curtas de inglês para português do Brasil, de forma "
    "natural e coloquial, como uma pessoa falaria. Responda APENAS com a "
    "tradução, sem aspas, sem explicações, sem repetir o texto original."
)


async def translate_to_pt_br(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    translated = await voicelive_text_completion(prompt=text, system=_SYSTEM_PROMPT)
    return translated or text
