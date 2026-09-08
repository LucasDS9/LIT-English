"""
Router da funcionalidade "Conversa - IA Tutor".

Fluxo (desde a migração para requisição única, ver README/CHANGELOG):
  1. Aluno grava um áudio (uma fala completa) no navegador.
  2. Frontend manda esse áudio pronto (arquivo inteiro) pro backend.
  3. Backend transcreve (Azure Speech, com fallback pro Whisper local --
     mesmo motor já usado no "Speak it!" dos exercícios).
  4. Backend manda a transcrição pra uma IA de texto (Groq) que devolve, numa
     única resposta: análise gramatical (erros + correção + feedback) E a
     resposta do tutor dando continuidade à conversa.
  5. Backend gera o áudio da fala do tutor (TTS clássico da Azure) e devolve
     tudo de uma vez pro frontend.

Isso substitui a arquitetura anterior (WebSocket + streaming de áudio ao vivo
pro modelo de voz em tempo real da Azure), que era frágil: o detector de
silêncio (VAD) da Azure não capturava a fala de forma confiável, e o
function-calling do modelo de voz frequentemente devolvia a análise
gramatical vazia mesmo quando havia erro na fala do aluno.

Endpoints:
  POST /conversation/turn      -> ESSENCIAL: manda o áudio, recebe transcrição + análise + resposta do tutor (+ áudio da resposta)
  POST /conversation/translate -> botão "Traduzir"
  POST /conversation/tts       -> botão "Ouvir"
  POST /conversation/end       -> encerrar sessão manualmente (zera o histórico)
  GET  /conversation/history   -> retomar histórico se sessão ainda ativa
"""

from __future__ import annotations

import base64
import logging
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.auth import get_current_approved_user
from app.models import User, UserRole
from app.language import student_language, student_source_language
from app.routers.pronunciation import transcribe

from ..services.conversation_ai import ConversationAiUnavailable, get_tutor_turn
from ..services.conversation_schemas import TranslateRequest, TranslateResponse, TTSRequest
from ..services.conversation_session_manager import conversation_sessions, ConversationTurn
from ..services.translation_service import translate_to_pt_br
from ..services.tts_service import synthesize_speech

logger = logging.getLogger("lit.conversation_router")

router = APIRouter(tags=["conversation"])

# Áudio menor que isso é quase certamente um toque acidental / gravação vazia
# -- evita gastar chamada de transcrição/IA à toa e dar um erro confuso.
_MIN_AUDIO_BYTES = 300

# Interjeições comuns que não carregam conteúdo linguístico. São removidas
# antes da análise para que "uh... hmm... I think..." não vire vocabulário/erro.
_FILLER_RE = re.compile(
    r"(?i)(?<![\wÀ-ÿ])(?:uh+|um+|umm+|uhm+|erm+|er+|hmm+|hm+|mmm+|mm+|ah+|eh+|ehm+|euh+)(?![\wÀ-ÿ])"
)
_NATIVE_HELP_RE = {
    "pt": re.compile(r"(?i)\b(?:como\s+(?:posso|eu\s+posso)\s+dizer|como\s+se\s+diz|como\s+digo|qual\s+(?:é|e)\s+a\s+palavra)\b"),
    "portugues": re.compile(r"(?i)\b(?:como\s+(?:posso|eu\s+posso)\s+dizer|como\s+se\s+diz|como\s+digo|qual\s+(?:é|e)\s+a\s+palavra)\b"),
}
_TARGET_HELP_RE = {
    "ingles": re.compile(r"(?i)\b(?:how\s+(?:can|do)\s+i\s+say|what\s+do\s+you\s+call)\b"),
    "italiano": re.compile(r"(?i)\b(?:come\s+(?:posso|si)\s+dire|come\s+si\s+dice)\b"),
    "frances": re.compile(r"(?i)\b(?:comment\s+(?:je\s+peux|dire)|comment\s+dit[- ]on)\b"),
    "espanhol": re.compile(r"(?i)\b(?:como\s+(?:puedo|se)\s+decir|como\s+se\s+dice)\b"),
    "alemao": re.compile(r"(?i)\b(?:wie\s+(?:kann\s+ich|sagt\s+man)|wie\s+sagt\s+man)\b"),
}


def _clean_transcript(text: str) -> str:
    """Remove hesitations/interjections without deleting real words."""
    text = (text or "").strip()
    if not text:
        return ""
    text = _FILLER_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:-")
    return text


def _looks_like_help_request(text: str, native: str, target: str) -> bool:
    if _NATIVE_HELP_RE.get(native, _NATIVE_HELP_RE["pt"]).search(text or ""):
        return True
    if _TARGET_HELP_RE.get(target, _TARGET_HELP_RE["ingles"]).search(text or ""):
        return True
    return False


def _pick_bilingual_transcript(target_text: str, native_text: str, native: str, target: str) -> str:
    """Prefer the native transcription only when it clearly captures a help request.

    Normal target-language conversation remains on the target transcript, avoiding
    the quality/cost penalty of replacing good target recognition with a weaker
    native-language pass.
    """
    target_text = _clean_transcript(target_text)
    native_text = _clean_transcript(native_text)
    if native_text and _looks_like_help_request(native_text, native, target):
        return native_text
    return target_text or native_text


def _speech_language(language: str) -> str:
    return {
        "ingles": "english", "italiano": "italian", "frances": "french",
        "espanhol": "spanish", "alemao": "german", "portugues": "portuguese",
    }.get(language, "english")


def _tts_locale(language: str) -> str:
    return {
        "ingles": "en-US", "italiano": "it-IT", "frances": "fr-FR",
        "espanhol": "es-ES", "alemao": "de-DE", "portugues": "pt-BR",
    }.get(language, "en-US")


def _require_student(user: User) -> None:
    if user.role != UserRole.aluno:
        raise HTTPException(status_code=403, detail="Apenas alunos podem usar a Conversa com IA Tutor.")
    if not user.is_approved:
        raise HTTPException(status_code=403, detail="Sua conta ainda não foi aprovada pelo professor.")


# --------------------------------------------------------------------------- #
# Endpoint principal: um turno completo da conversa
# --------------------------------------------------------------------------- #

@router.post("/conversation/turn")
async def conversation_turn(
    audio: UploadFile = File(...),
    level: str | None = Form(None),
    target_language: str | None = Form(None),
    native_language: str | None = Form(None),
    user: User = Depends(get_current_approved_user),
):
    _require_student(user)

    student_id = str(user.id)
    target = (target_language or student_language(user) or "ingles").strip().lower()
    native = (native_language or student_source_language(user) or "pt").strip().lower()
    aliases = {
        "en": "ingles", "english": "ingles", "it": "italiano", "italian": "italiano",
        "fr": "frances", "french": "frances", "es": "espanhol", "spanish": "espanhol",
        "de": "alemao", "german": "alemao", "pt": "portugues", "portuguese": "portugues",
    }
    target = aliases.get(target, target)
    native = aliases.get(native, native)
    allowed = {"ingles", "italiano", "frances", "espanhol", "alemao", "portugues"}
    if target not in allowed:
        raise HTTPException(status_code=400, detail="Língua-alvo não suportada para a conversa.")
    if native not in allowed:
        raise HTTPException(status_code=400, detail="Língua nativa não suportada para a conversa.")
    audio_bytes = await audio.read()

    if len(audio_bytes) < _MIN_AUDIO_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Áudio muito curto. Segure o botão e fale um pouco mais.",
        )

    # 1) Transcrição -- normalmente na língua-alvo, mas fazemos uma segunda
    #    leitura na língua nativa quando as duas são diferentes. Isso permite
    #    frases como "como posso dizer pedra em italiano?" e "how can I say
    #    pedra in English?" sem perder o sentido da pergunta.
    try:
        target_transcript = transcribe(audio_bytes, _speech_language(target))
        native_transcript = ""
        if native != target:
            try:
                native_transcript = transcribe(audio_bytes, _speech_language(native))
            except Exception:
                logger.warning("Falha na segunda transcrição na língua nativa", exc_info=True)
        student_transcript = _pick_bilingual_transcript(
            target_transcript, native_transcript, native, target
        )
    except Exception:
        logger.exception("Falha na transcrição do áudio (aluno=%s)", student_id)
        raise HTTPException(
            status_code=502,
            detail="Não consegui processar o áudio agora. Tente novamente em alguns segundos.",
        )

    student_transcript = _clean_transcript(student_transcript)
    if not student_transcript:
        raise HTTPException(
            status_code=422,
            detail="Não consegui entender o que você disse. Tente falar mais perto do microfone, num lugar mais silencioso.",
        )

    session = await conversation_sessions.get_or_create(
        student_id=student_id,
        student_name=user.name,
        level=level,
        target_language=target,
        native_language=native,
    )

    # 2) Análise gramatical + resposta do tutor (uma única chamada de IA em texto)
    try:
        result = get_tutor_turn(
            student_name=user.name,
            student_text=student_transcript,
            history=session.history_for_ai(),
            level=session.level,
            target_language=session.target_language,
            native_language=session.native_language,
        )
    except ConversationAiUnavailable:
        logger.exception("IA de conversa indisponível (aluno=%s)", student_id)
        raise HTTPException(
            status_code=502,
            detail="A IA está indisponível no momento. Tente novamente em instantes.",
        )

    analysis = {
        "student_transcript": student_transcript,
        "errors": result["errors"],
        "corrected_sentence": result["corrected_sentence"],
        "feedback_native": result.get("feedback_native", result.get("feedback_pt_br", "")),
        "feedback_pt_br": result.get("feedback_pt_br", result.get("feedback_native", "")),
    }
    tutor_reply = result["tutor_reply"]

    await conversation_sessions.record_turn(
        student_id, ConversationTurn(role="student", text=student_transcript, analysis=analysis)
    )
    await conversation_sessions.record_turn(
        student_id, ConversationTurn(role="tutor", text=tutor_reply)
    )

    # 3) Áudio da resposta do tutor (best-effort -- se o TTS falhar, ainda
    #    devolvemos texto + análise; o frontend só não toca áudio automático).
    tutor_audio_b64 = None
    try:
        audio_bytes_reply = await synthesize_speech(tutor_reply, _tts_locale(target))
        tutor_audio_b64 = base64.b64encode(audio_bytes_reply).decode("ascii")
    except Exception:
        logger.warning("Falha ao gerar áudio da resposta do tutor (aluno=%s)", student_id, exc_info=True)

    return {
        "student_transcript": student_transcript,
        "analysis": analysis,
        "tutor_reply": tutor_reply,
        "tutor_audio_b64": tutor_audio_b64,
    }


# --------------------------------------------------------------------------- #
# REST auxiliares
# --------------------------------------------------------------------------- #

@router.post("/conversation/translate", response_model=TranslateResponse)
async def translate_message(
    payload: TranslateRequest,
    user: User = Depends(get_current_approved_user),
):
    # O idioma nativo enviado pela tela é usado quando presente; o cadastro do
    # aluno continua sendo o fallback seguro.
    native = (payload.native_language or student_source_language(user) or "pt").strip().lower()
    aliases = {
        "en": "ingles", "english": "ingles", "it": "italiano", "italian": "italiano",
        "fr": "frances", "french": "frances", "es": "espanhol", "spanish": "espanhol",
        "de": "alemao", "german": "alemao", "pt": "portugues", "pt-br": "portugues",
        "portuguese": "portugues",
    }
    native = aliases.get(native, native)
    translated = await translate_to_pt_br(payload.text, native)
    return TranslateResponse(original=payload.text, translated=translated)


@router.post("/conversation/tts")
async def tts_endpoint(
    payload: TTSRequest,
    user: User = Depends(get_current_approved_user),
):
    try:
        audio_bytes = await synthesize_speech(payload.text, payload.lang)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao gerar áudio: {exc}")
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/conversation/end")
async def end_conversation(user: User = Depends(get_current_approved_user)):
    await conversation_sessions.end_session(str(user.id))
    return {"status": "ended"}


@router.get("/conversation/history")
async def conversation_history(user: User = Depends(get_current_approved_user)):
    session = conversation_sessions.get(str(user.id))
    if not session:
        return {"active": False, "history": []}
    return {
        "active": True,
        "history": [
            {
                "role": t.role,
                "text": t.text,
                "analysis": t.analysis,
                "at": t.at.isoformat(),
            }
            for t in session.history
        ],
    }
