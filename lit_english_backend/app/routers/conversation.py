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

import asyncio
import base64
import logging
import os
import re
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_current_approved_user
from app.models import AIUsageLog, User, UserRole
from app.database import get_db
from app.language import student_language, student_source_language
from app.routers.pronunciation import transcribe_with_confidence, detect_spoken_language

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



# Probabilidade mínima do LID do Whisper pra confiarmos nele como sinal
# decisivo. Abaixo disso, o áudio é curto/ambíguo demais e caímos no
# fallback de confiança entre as duas passadas.
_LID_MIN_PROBABILITY = 0.55

_CONFIDENCE_MARGIN = 0.15


def _pick_bilingual_transcript(
    target_text: str,
    native_text: str,
    native: str,
    target: str,
    target_confidence: float | None = None,
    native_confidence: float | None = None,
    detected_language: str | None = None,
    detected_probability: float = 0.0,
) -> str:
    """Escolhe qual das duas transcrições (língua-alvo x língua nativa) usar.

    Ordem de decisão (do sinal mais barato/específico pro mais genérico):
      1. Fórmula explícita de ajuda ("como se diz", "how can I say") na
         transcrição nativa -- cobre frases mescladas.
      2. Identificação automática de idioma feita pelo Whisper sobre o
         áudio bruto (sem forçar língua nenhuma) -- é o sinal "de verdade"
         de que língua o aluno falou, equivalente ao que o realtime da
         OpenAI faz. Usado sempre que a probabilidade é razoável.
      3. Comparação de confiança entre as duas passadas fixas, só como
         último recurso (ex.: Whisper indisponível).
    """
    target_text = _clean_transcript(target_text)
    native_text = _clean_transcript(native_text)

    if not native_text:
        return target_text
    if not target_text:
        return native_text

    if _looks_like_help_request(native_text, native, target):
        return native_text

    if detected_language and detected_probability >= _LID_MIN_PROBABILITY:
        if detected_language == native and native != target:
            return native_text
        if detected_language == target:
            return target_text
        # Detectou uma terceira língua (nem native nem target) -- não temos
        # transcrição pra ela, então segue pro fallback de confiança abaixo.

    if target_confidence is not None and native_confidence is not None:
        if native_confidence > target_confidence + _CONFIDENCE_MARGIN:
            return native_text
        if target_confidence > native_confidence + _CONFIDENCE_MARGIN:
            return target_text

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
    audio_duration: float | None = Form(None),
    user: User = Depends(get_current_approved_user),
    db: Session = Depends(get_db),
):
    _require_student(user)

    turn_start = time.perf_counter()
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
    upload_start = time.perf_counter()
    audio_bytes = await audio.read()
    upload_ms = (time.perf_counter() - upload_start) * 1000
    audio_seconds = max(0.0, float(audio_duration or 0.0))

    if len(audio_bytes) < _MIN_AUDIO_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Áudio muito curto. Segure o botão e fale um pouco mais.",
        )

    def _record(status: str, error_type: str | None = None, **extra):
        try:
            db.add(AIUsageLog(
                student_id=user.id,
                endpoint="conversation/turn",
                status=status,
                error_type=error_type,
                upload_ms=upload_ms,
                total_ms=(time.perf_counter() - turn_start) * 1000,
                audio_seconds=audio_seconds,
                **extra,
            ))
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("Falha ao registrar telemetria do turno", exc_info=True)

    # 1) Transcrição -- normalmente na língua-alvo, mas fazemos uma segunda
    #    leitura na língua nativa quando as duas são diferentes, MAIS uma
    #    detecção automática de idioma (Whisper LID, sem forçar língua) que é
    #    o sinal decisivo de verdade -- é isso que permite entender o aluno
    #    falando inteiramente na língua nativa, sem nenhuma fórmula de ajuda,
    #    e sem depender de heurística de confiança frágil.
    #
    #    Duas otimizações de latência aqui:
    #      a) a segunda transcrição (língua nativa) e a detecção automática
    #         de idioma (Whisper local, rodando em CPU) não dependem uma da
    #         outra -- antes rodavam em série, agora rodam em paralelo com
    #         asyncio.gather (via to_thread, já que as duas são bloqueantes).
    #      b) se a transcrição na língua-alvo já veio com confiança alta, o
    #         áudio quase certamente NÃO é um pedido de ajuda na língua
    #         nativa nem uma fala mista -- pulamos a segunda transcrição e o
    #         Whisper LID inteiramente, que juntos são o trecho mais caro
    #         do turno.
    _HIGH_CONFIDENCE_SKIP_BILINGUAL = 0.85

    try:
        stt_start = time.perf_counter()
        target_transcript, target_confidence, target_provider = await asyncio.to_thread(
            transcribe_with_confidence, audio_bytes, _speech_language(target), True
        )

        native_transcript = ""
        native_confidence: float | None = None
        detected_language: str | None = None
        detected_probability = 0.0

        needs_bilingual_check = native != target and (
            target_confidence is None or target_confidence < _HIGH_CONFIDENCE_SKIP_BILINGUAL
        )

        if needs_bilingual_check:
            async def _native_transcript_task():
                try:
                    return await asyncio.to_thread(
                        transcribe_with_confidence, audio_bytes, _speech_language(native)
                    )
                except Exception:
                    logger.warning("Falha na segunda transcrição na língua nativa", exc_info=True)
                    return "", None

            async def _detect_language_task():
                try:
                    return await asyncio.to_thread(detect_spoken_language, audio_bytes)
                except Exception:
                    logger.warning("Falha na detecção automática de idioma", exc_info=True)
                    return None, 0.0

            (native_transcript, native_confidence), (detected_language, detected_probability) = (
                await asyncio.gather(_native_transcript_task(), _detect_language_task())
            )

        stt_ms = (time.perf_counter() - stt_start) * 1000
        student_transcript = _pick_bilingual_transcript(
            target_transcript,
            native_transcript,
            native,
            target,
            target_confidence,
            native_confidence,
            detected_language,
            detected_probability,
        )
    except Exception:
        logger.exception("Falha na transcrição do áudio (aluno=%s)", student_id)
        _record("error", "stt")
        raise HTTPException(
            status_code=502,
            detail="Não consegui processar o áudio agora. Tente novamente em alguns segundos.",
        )

    raw_transcript = _clean_transcript(student_transcript)
    if not raw_transcript:
        _record("error", "empty_transcript", stt_ms=stt_ms, stt_provider=target_provider, stt_fallback=(target_provider == "whisper"))
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

    # 2) Análise gramatical + resposta do tutor (uma única chamada de IA em texto).
    #    Mandamos a transcrição BRUTA (raw_transcript) pro Groq -- ele foi
    #    instruído a reinterpretar prováveis erros de reconhecimento de voz
    #    usando o contexto da conversa (ver understood_transcript no prompt),
    #    então é ele quem decide a versão final "entendida" da fala.
    llm_start = time.perf_counter()
    try:
        result = await get_tutor_turn(
            student_name=user.name,
            student_text=raw_transcript,
            history=session.history_for_ai(),
            level=session.level,
            target_language=session.target_language,
            native_language=session.native_language,
        )
    except ConversationAiUnavailable:
        llm_ms = (time.perf_counter() - llm_start) * 1000
        logger.exception("IA de conversa indisponível (aluno=%s)", student_id)
        _record("error", "llm", stt_ms=stt_ms, stt_provider=target_provider, stt_fallback=(target_provider == "whisper"), llm_ms=llm_ms, llm_provider="groq", llm_model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
        raise HTTPException(
            status_code=502,
            detail="A IA está indisponível no momento. Tente novamente em instantes.",
        )
    llm_ms = (time.perf_counter() - llm_start) * 1000

    # A partir daqui, usamos a versão "entendida" (corrigida pelo contexto)
    # como o texto oficial do turno -- tanto pro que aparece na tela quanto
    # pro histórico que alimenta os PRÓXIMOS turnos. Isso evita que um erro
    # de ASR (ex.: "petra" em vez de "pedra") fique se arrastando e
    # confundindo a IA turno após turno. Se o modelo não devolver nada
    # utilizável em understood_transcript, caímos de volta pra transcrição
    # bruta.
    student_transcript = result.get("understood_transcript") or raw_transcript

    analysis = {
        "student_transcript": student_transcript,
        "raw_transcript": raw_transcript,
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
    tts_start = time.perf_counter()
    tts_error = None
    try:
        audio_bytes_reply = await synthesize_speech(tutor_reply, _tts_locale(target))
        tutor_audio_b64 = base64.b64encode(audio_bytes_reply).decode("ascii")
    except Exception as exc:
        tts_error = type(exc).__name__
        logger.warning("Falha ao gerar áudio da resposta do tutor (aluno=%s)", student_id, exc_info=True)
    tts_ms = (time.perf_counter() - tts_start) * 1000

    usage = result.get("usage") or {}
    _record(
        "partial" if tts_error else "success",
        tts_error,
        stt_ms=stt_ms,
        stt_provider=target_provider,
        stt_fallback=(target_provider == "whisper"),
        llm_ms=llm_ms,
        llm_provider="groq",
        llm_model=usage.get("model") or os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
        tts_ms=tts_ms,
        tts_provider="azure" if tutor_audio_b64 else None,
        tts_characters=len(tutor_reply),
    )

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
