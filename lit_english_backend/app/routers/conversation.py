"""
Router da funcionalidade "Conversa - IA Tutor".

Endpoints:
  WS   /ws/conversation                -> conversa em tempo real (áudio + análise)
  POST /conversation/translate         -> botão "Traduzir"
  POST /conversation/tts               -> botão "Ouvir"
  POST /conversation/end               -> encerrar sessão manualmente
  GET  /conversation/history           -> retomar histórico se sessão ainda ativa

Autenticação:
  - Endpoints REST usam o mesmo esquema JWT do resto da API (Authorization: Bearer <token>).
  - O WebSocket não consegue mandar header Authorization a partir do browser,
    então o token é passado via query string (?token=...) e validado manualmente
    aqui com o mesmo SECRET_KEY/ALGORITHM usados em app.auth.
  - O aluno (student_id / student_name) SEMPRE vem do token validado -- nunca de
    um parâmetro que o cliente possa forjar.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, Query, status
from fastapi.responses import Response
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth import ALGORITHM, SECRET_KEY, get_current_approved_user
from app.database import get_db
from app.models import User, UserRole

from ..services.conversation_session_manager import (
    conversation_sessions,
    ConversationTurn,
)
from ..services.conversation_schemas import TranslateRequest, TranslateResponse, TTSRequest
from ..services.translation_service import translate_to_pt_br
from ..services.tts_service import synthesize_speech
from ..services.voice_live_client import (
    SPEECH_ANALYSIS_TOOL_NAME,
    extract_inline_tool_calls,
    split_safe_tail,
)

logger = logging.getLogger("lit.conversation_router")

router = APIRouter(tags=["conversation"])


def _get_ws_user(token: str, db: Session) -> User | None:
    """Valida o JWT do WebSocket manualmente (não dá pra usar Depends(oauth2_scheme) aqui,
    já que o browser não manda header Authorization em conexões WebSocket)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.id == int(user_id)).first()
    return user


def _ensure_can_use_conversation(user: User | None) -> str | None:
    """Retorna uma mensagem de erro se o usuário não puder usar o módulo, ou None se puder."""
    if user is None:
        return "Sessão expirada. Faça login novamente."
    if user.role != UserRole.aluno:
        return "Apenas alunos podem usar a Conversa com IA Tutor."
    if not user.is_approved:
        return "Sua conta ainda não foi aprovada pelo professor."
    return None


# --------------------------------------------------------------------------- #
# WebSocket principal: ponte entre o navegador do aluno e a Azure Voice Live
# --------------------------------------------------------------------------- #

@router.websocket("/ws/conversation")
async def conversation_ws(
    websocket: WebSocket,
    token: str = Query(..., description="JWT do aluno logado (mesmo token do resto da API)"),
    level: str | None = Query(None, description="Nível estimado do aluno, opcional"),
    voice: str | None = Query(None, description="Voz Azure TTS a usar, opcional"),
    db: Session = Depends(get_db),
):
    await websocket.accept()

    user = _get_ws_user(token, db)
    error_msg = _ensure_can_use_conversation(user)
    if error_msg:
        await websocket.send_json({"type": "error", "message": error_msg})
        await websocket.close()
        return

    student_id = str(user.id)
    student_name = user.name

    try:
        session = await conversation_sessions.get_or_create(
            student_id=student_id, student_name=student_name, voice=voice, level=level
        )
    except Exception as exc:
        logger.exception("Falha ao abrir sessão Voice Live")
        await websocket.send_json({"type": "error", "message": f"Falha ao conectar à IA: {exc}"})
        await websocket.close()
        return

    await websocket.send_json({"type": "session_ready"})

    # Estado do turno de resposta do tutor sendo montado (texto acumulado por deltas)
    tutor_text_buffer = {"text": ""}
    pending_call = {"call_id": None, "name": None, "args_buffer": ""}

    # Buffer usado pra filtrar chamadas de "report_speech_analysis(...)" que
    # o modelo às vezes escreve como texto solto dentro do transcript da
    # fala dele, em vez de usar o protocolo estruturado de function-calling
    # (ver extract_inline_tool_calls em voice_live_client.py).
    inline_call_pending = {"text": ""}

    # O modelo às vezes repete a MESMA chamada de análise duas vezes seguidas
    # (visto em produção). Isso evita mandar duas bolhas idênticas pro aluno.
    last_analysis = {"json": None}

    async def handle_speech_analysis(analysis: dict) -> None:
        """Único ponto que trata uma análise de fala, venha ela do protocolo
        estruturado de tool-calling ou "vazada" como texto (ver acima)."""
        analysis_json = json.dumps(analysis, sort_keys=True)
        if analysis_json == last_analysis["json"]:
            return  # duplicata idêntica à análise anterior -- ignora
        last_analysis["json"] = analysis_json

        await websocket.send_json({"type": "speech_analysis", "analysis": analysis})
        await conversation_sessions.record_turn(
            student_id,
            ConversationTurn(
                role="student",
                text=analysis.get("student_transcript", ""),
                analysis=analysis,
            ),
        )

    async def reader():
        """Frontend -> backend -> Azure (áudio/texto do aluno)."""
        try:
            while True:
                msg = await websocket.receive_text()
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError:
                    continue

                await conversation_sessions.touch(student_id)
                mtype = data.get("type")

                if mtype == "audio_chunk":
                    import base64
                    audio_b64 = data.get("audio_b64", "")
                    if audio_b64:
                        pcm16 = base64.b64decode(audio_b64)
                        await session.voice_live.send_audio_chunk(pcm16)

                elif mtype == "end_turn":
                    await session.voice_live.commit_audio()

                elif mtype == "text_message":
                    text = (data.get("text") or "").strip()
                    if text:
                        await conversation_sessions.record_turn(
                            student_id, ConversationTurn(role="student", text=text)
                        )
                        await session.voice_live.send_text_message(text)

                elif mtype == "ping":
                    pass  # só mantém viva / atualiza last_activity acima

        except WebSocketDisconnect:
            logger.info("Aluno %s desconectou do WS (sessão de IA continua ativa por %smin)",
                        student_id, conversation_sessions.timeout_minutes)
        except Exception:
            logger.exception("Erro no reader do WS de conversa (aluno=%s)", student_id)

    async def forwarder():
        """Azure -> backend -> frontend (transcrição, análise, texto e áudio do tutor)."""
        try:
            async for event in session.voice_live.events():
                etype = event.type
                raw = event.raw

                if etype == "conversation.item.input_audio_transcription.completed":
                    transcript = raw.get("transcript", "")
                    await websocket.send_json({"type": "student_transcript", "text": transcript})

                elif etype == "response.function_call_arguments.delta":
                    if raw.get("name") == SPEECH_ANALYSIS_TOOL_NAME or pending_call["call_id"] == raw.get("call_id"):
                        pending_call["call_id"] = raw.get("call_id")
                        pending_call["name"] = raw.get("name", pending_call["name"])
                        pending_call["args_buffer"] += raw.get("delta", "")

                elif etype == "response.function_call_arguments.done":
                    call_id = raw.get("call_id") or pending_call["call_id"]
                    args_str = raw.get("arguments") or pending_call["args_buffer"]
                    try:
                        analysis = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        analysis = {}

                    if analysis:
                        await handle_speech_analysis(analysis)

                    if call_id:
                        await session.voice_live.submit_tool_output(call_id, {"status": "received"})
                    pending_call["call_id"] = None
                    pending_call["name"] = None
                    pending_call["args_buffer"] = ""

                elif etype == "response.audio_transcript.delta":
                    delta = raw.get("delta", "")

                    # Junta com o que ficou pendente do delta anterior (podia
                    # ser o começo de uma chamada tipo "report_speech_ana...")
                    chunk = inline_call_pending["text"] + delta
                    calls, clean_text, pending = extract_inline_tool_calls(
                        chunk, SPEECH_ANALYSIS_TOOL_NAME
                    )

                    for analysis in calls:
                        if analysis:
                            await handle_speech_analysis(analysis)

                    # mesmo sem chamada em andamento, o final do texto pode
                    # ser o início de uma nova chamada chegando aos poucos --
                    # não mostra esse pedacinho ainda, guarda pro próximo delta
                    safe_text, tail_pending = split_safe_tail(
                        clean_text, f"{SPEECH_ANALYSIS_TOOL_NAME}("
                    )
                    inline_call_pending["text"] = pending + tail_pending

                    if safe_text:
                        tutor_text_buffer["text"] += safe_text
                        await websocket.send_json({"type": "tutor_text_delta", "delta": safe_text})

                elif etype == "response.audio.delta":
                    audio_b64 = raw.get("delta", "")
                    if audio_b64:
                        await websocket.send_json({"type": "tutor_audio_chunk", "audio_b64": audio_b64})

                elif etype == "response.audio.done":
                    await websocket.send_json({"type": "tutor_audio_done"})

                elif etype == "response.done":
                    # Se sobrou algo pendente (ex: resposta terminou bem no
                    # meio do que parecia o início de uma chamada, mas nunca
                    # fechou), manda como texto normal em vez de perder.
                    leftover = inline_call_pending["text"]
                    inline_call_pending["text"] = ""
                    if leftover:
                        tutor_text_buffer["text"] += leftover
                        await websocket.send_json({"type": "tutor_text_delta", "delta": leftover})

                    final_text = tutor_text_buffer["text"]
                    if final_text:
                        await conversation_sessions.record_turn(
                            student_id, ConversationTurn(role="tutor", text=final_text)
                        )
                    await websocket.send_json({"type": "tutor_text_done", "text": final_text})
                    tutor_text_buffer["text"] = ""

                elif etype == "error":
                    error_code = raw.get("error", {}).get("code")

                    if error_code == "input_audio_buffer_commit_empty":
                        # Não é fatal: só significa que um "end_turn" chegou
                        # com o buffer de áudio vazio (gravação curta demais,
                        # ou algum chunk que não chegou a tempo). A sessão
                        # continua normal, então só loga -- não assusta o
                        # aluno com uma mensagem de erro na tela.
                        logger.info(
                            "Commit de áudio vazio ignorado (aluno=%s): %s",
                            student_id, raw.get("error", {}).get("message"),
                        )
                        continue

                    logger.warning("Erro vindo da Voice Live (aluno=%s): %s", student_id, raw)
                    await websocket.send_json({
                        "type": "error",
                        "message": raw.get("error", {}).get("message", "Erro na IA."),
                    })

                # outros tipos de evento (session.created, input_audio_buffer.speech_started, etc.)
                # são ignorados propositalmente -- adicione aqui se o frontend precisar deles.

        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("Erro no forwarder do WS de conversa (aluno=%s)", student_id)

    reader_task = asyncio.create_task(reader())

    # Se essa sessão já tinha uma tarefa "escutando" a Azure de uma conexão
    # anterior (aluno deu refresh, trocou de rede, etc.), garante que ela
    # terminou de VERDADE antes de começar a escutar de novo -- senão as
    # duas concorrem pela mesma conexão com a Azure e a IA para de responder
    # (ver comentário em ConversationSession.active_forwarder_task).
    old_forwarder = session.active_forwarder_task
    if old_forwarder is not None and not old_forwarder.done():
        old_forwarder.cancel()
        try:
            await old_forwarder
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Erro ao encerrar forwarder anterior (aluno=%s)", student_id)

    forwarder_task = asyncio.create_task(forwarder())
    session.active_forwarder_task = forwarder_task

    done, pending = await asyncio.wait(
        {reader_task, forwarder_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()

    if session.active_forwarder_task is forwarder_task:
        session.active_forwarder_task = None

    # Nota: não encerramos a sessão Voice Live aqui de propósito -- o aluno pode
    # ter caído a conexão (troca de rede, celular bloqueou) e volta em seguida.
    # Quem encerra de fato é o loop de inatividade de 30min, ou o endpoint
    # /conversation/end quando o aluno sai da tela conscientemente.


# --------------------------------------------------------------------------- #
# REST auxiliares (protegidos pelo mesmo JWT do resto da API)
# --------------------------------------------------------------------------- #

@router.post("/conversation/translate", response_model=TranslateResponse)
async def translate_message(
    payload: TranslateRequest,
    user: User = Depends(get_current_approved_user),
):
    translated = await translate_to_pt_br(payload.text)
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
    session = conversation_sessions._sessions.get(str(user.id))  # leitura simples, ok para GET
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
