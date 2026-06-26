"""
Rota de Text-to-Speech (pronúncia em inglês dos flashcards).

O navegador não consegue chamar o serviço público do Google Translate TTS
diretamente via fetch() porque ele não envia headers de CORS. Por isso o
backend funciona como "proxy": recebe o texto, busca o áudio MP3 no Google
e devolve para o frontend. Isso também evita expor a chamada externa no
cliente e permite cachear os áudios mais usados em memória.

Não usa nenhuma chave de API — é o mesmo endpoint não-oficial que o próprio
Google Translate usa no navegador (client=tw-ob).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
import httpx

from app.auth import get_current_approved_user
from app.models import User

router = APIRouter(prefix="/tts", tags=["TTS"])

GOOGLE_TTS_URL = "https://translate.google.com/translate_tts"

# O serviço do Google corta o texto em ~200 caracteres; nossos flashcards
# são frases curtas então isso nunca deve ser um problema na prática.
MAX_TEXT_LENGTH = 200

# Cache simples em memória (processo único). Reinicia quando o servidor reinicia.
_audio_cache: dict[str, bytes] = {}
_CACHE_MAX_ITEMS = 500


@router.get("/speak")
async def speak(
    text: str = Query(..., min_length=1, max_length=MAX_TEXT_LENGTH),
    _user: User = Depends(get_current_approved_user),
):
    """
    Retorna um áudio MP3 com a pronúncia em inglês do texto enviado.
    Usado pelo botão de "ouvir pronúncia" na tela de revisão de flashcards.
    """
    cache_key = text.strip().lower()

    if cache_key in _audio_cache:
        return Response(content=_audio_cache[cache_key], media_type="audio/mpeg")

    params = {
        "ie": "UTF-8",
        "q": text,
        "tl": "en-US",
        "client": "tw-ob",
    }
    headers = {
        # O serviço bloqueia requisições sem um User-Agent de navegador.
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://translate.google.com/",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(GOOGLE_TTS_URL, params=params, headers=headers)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível gerar o áudio agora. Tente novamente.",
        )

    if response.status_code != 200 or not response.content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível gerar o áudio agora. Tente novamente.",
        )

    audio_bytes = response.content

    if len(_audio_cache) >= _CACHE_MAX_ITEMS:
        _audio_cache.pop(next(iter(_audio_cache)))
    _audio_cache[cache_key] = audio_bytes

    return Response(content=audio_bytes, media_type="audio/mpeg")
