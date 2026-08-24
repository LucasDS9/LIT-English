"""
Cliente assíncrono para a Azure Voice Live API usando o modelo phi4-mm-realtime.

Este módulo NÃO conhece FastAPI nem o frontend -- ele só sabe conversar com a
Azure via WebSocket usando os eventos estilo "Realtime API" (session.update,
input_audio_buffer.append, response.create, etc). Quem orquestra a ponte
frontend <-> Azure é o `routers/conversation.py`.

Referência dos eventos: Azure AI Voice Live API (WebSocket), modelo phi4-mm-realtime.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol

from . import voice_config as cfg

logger = logging.getLogger("lit.voicelive")

# Nome da "function tool" que o modelo chama para reportar a análise de fala.
# É assim que conseguimos, com o MESMO modelo (phi4-mm-realtime) que já está
# ouvindo o áudio, obter uma análise estruturada (erro + explicação + correção)
# em vez de precisar de uma segunda chamada a outro serviço de IA.
SPEECH_ANALYSIS_TOOL_NAME = "report_speech_analysis"

SPEECH_ANALYSIS_TOOL_SCHEMA = {
    "type": "function",
    "name": SPEECH_ANALYSIS_TOOL_NAME,
    "description": (
        "Chame esta função SEMPRE que o aluno terminar de falar em inglês, "
        "antes de responder a ele. Analise a fala transcrita do aluno em "
        "busca de erros de gramática, vocabulário ou pronúncia (com base na "
        "transcrição). Se não houver nenhum erro, envie errors como lista vazia."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "student_transcript": {
                "type": "string",
                "description": "Transcrição exata do que o aluno disse.",
            },
            "errors": {
                "type": "array",
                "description": "Lista de erros encontrados na fala do aluno.",
                "items": {
                    "type": "object",
                    "properties": {
                        "wrong_fragment": {
                            "type": "string",
                            "description": "Trecho exato que está errado, ex: 'goed'.",
                        },
                        "correct_fragment": {
                            "type": "string",
                            "description": "Como deveria ser, ex: 'went'.",
                        },
                        "explanation_pt_br": {
                            "type": "string",
                            "description": "Explicação curta em português do Brasil.",
                        },
                    },
                    "required": ["wrong_fragment", "correct_fragment", "explanation_pt_br"],
                },
            },
            "corrected_sentence": {
                "type": "string",
                "description": "A frase do aluno reescrita corretamente, em inglês.",
            },
            "feedback_pt_br": {
                "type": "string",
                "description": (
                    "Feedback curto, encorajador, em português do Brasil, "
                    "sobre a fala do aluno como um todo."
                ),
            },
        },
        "required": ["student_transcript", "errors", "corrected_sentence", "feedback_pt_br"],
    },
}


def build_tutor_instructions(student_name: str, level: str | None = None) -> str:
    """Prompt de sistema enviado na session.update."""
    level_txt = f"O nível estimado do aluno é {level}. " if level else ""
    return (
        f"Você é o IA Tutor da plataforma LIT English, conversando em inglês por voz "
        f"com o aluno {student_name}. {level_txt}"
        "Regras:\n"
        "1. Fale APENAS em inglês nas suas respostas faladas ao aluno (nunca em português).\n"
        "2. Mantenha uma conversa natural, curta e adequada ao nível do aluno, "
        "fazendo perguntas de acompanhamento sobre o que ele disse.\n"
        f"3. Sempre que o aluno terminar de falar, chame a função "
        f"'{SPEECH_ANALYSIS_TOOL_NAME}' com a análise da fala dele ANTES de "
        "gerar a resposta falada.\n"
        "4. Depois de chamar a função, responda ao aluno com uma frase curta em "
        "inglês, dando continuidade à conversa (não repita a correção em voz alta, "
        "ela já aparece na tela).\n"
        "5. Seja gentil e encorajador, é um ambiente de aprendizado."
    )


def default_session_config(student_name: str, voice: str, level: str | None = None) -> dict:
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "model": cfg.VOICELIVE_MODEL,
            "instructions": build_tutor_instructions(student_name, level),
            "voice": {
                "type": "azure-standard",
                "name": voice,
            },
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "input_audio_transcription": {
                "model": "azure-speech",
            },
            "turn_detection": {
                "type": "azure_semantic_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
            },
            "tools": [SPEECH_ANALYSIS_TOOL_SCHEMA],
            "tool_choice": "auto",
        },
    }


def extract_inline_tool_calls(text: str, tool_name: str) -> tuple[list[dict], str, str]:
    """
    Alguns modelos (ex: phi4-mm-realtime) às vezes não usam o protocolo
    estruturado de function-calling da Voice Live (eventos
    'response.function_call_arguments.*') e em vez disso "falam"/escrevem o
    texto literal da chamada, tipo:

        report_speech_analysis({"student_transcript": "...", ...})

    dentro do próprio 'response.audio_transcript.delta' -- que é o texto
    que vira a bolha de fala do tutor. Essa função varre um texto acumulado
    em busca desse padrão, extrai e faz o parse do(s) JSON, e devolve:

      - calls: lista de dicts já parseados (uma por chamada completa encontrada)
      - clean_text: o texto SEM as chamadas (o que é seguro mostrar ao aluno)
      - pending: um trecho no final do texto que pode ser o COMEÇO de uma
                 chamada ainda incompleta (o modelo ainda está "digitando"
                 o resto) -- não deve ser exibido ainda; deve ser prependado
                 no próximo pedaço de texto que chegar e processado de novo.
    """
    marker = f"{tool_name}("
    calls: list[dict] = []
    out_parts: list[str] = []
    i = 0

    while True:
        idx = text.find(marker, i)
        if idx == -1:
            out_parts.append(text[i:])
            return calls, "".join(out_parts), ""

        out_parts.append(text[i:idx])

        # acha o parêntese de fechamento correspondente (contando aninhamento)
        paren_start = idx + len(marker) - 1
        depth = 0
        end = None
        j = paren_start
        while j < len(text):
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
                if depth == 0:
                    end = j
                    break
            j += 1

        if end is None:
            # chamada ainda incompleta (mais deltas vão chegar) -- devolve
            # tudo que já é seguro mostrar, e guarda o resto como pendente
            return calls, "".join(out_parts), text[idx:]

        inner = text[paren_start + 1 : end]
        try:
            calls.append(json.loads(inner))
        except json.JSONDecodeError:
            logger.warning("Não consegui parsear chamada inline de %s: %r", tool_name, inner)

        i = end + 1


def split_safe_tail(text: str, marker: str) -> tuple[str, str]:
    """
    Mesmo sem nenhuma chamada em andamento, o FINAL de 'text' pode ser o
    início de um novo 'report_speech_analysis(' que ainda está chegando aos
    poucos (delta por delta). Se mostrássemos esse pedaço agora, o aluno
    veria por uma fração de segundo um "report_spe" solto na tela.

    Devolve (parte_segura_para_mostrar, parte_a_reter_para_o_proximo_delta).
    """
    max_check = min(len(marker) - 1, len(text))
    for size in range(max_check, 0, -1):
        if marker.startswith(text[-size:]):
            return text[:-size], text[-size:]
    return text, ""


@dataclass
class VoiceLiveEvent:
    type: str
    raw: dict = field(default_factory=dict)


class VoiceLiveSession:
    """
    Uma conexão WebSocket com a Azure Voice Live API, para UM aluno.

    Uso típico:
        session = VoiceLiveSession(student_name="Lucas")
        await session.connect()
        await session.configure()
        ...
        await session.send_audio_chunk(pcm16_bytes)
        async for event in session.events():
            ...
        await session.close()
    """

    def __init__(
        self,
        student_name: str,
        voice: str | None = None,
        level: str | None = None,
    ):
        self.student_name = student_name
        self.voice = voice or cfg.DEFAULT_TUTOR_VOICE
        self.level = level
        self.ws: Optional[WebSocketClientProtocol] = None
        self._closed = False

    def _url(self) -> str:
        return (
            f"{cfg.VOICELIVE_WS_BASE}"
            f"?api-version={cfg.VOICELIVE_API_VERSION}"
            f"&model={cfg.VOICELIVE_MODEL}"
        )

    async def connect(self) -> None:
        cfg.require_configured()
        headers = {"api-key": cfg.VOICELIVE_API_KEY}
        logger.info("Conectando à Voice Live API (aluno=%s)", self.student_name)
        self.ws = await websockets.connect(
            self._url(),
            additional_headers=headers,
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
        )

    async def configure(self) -> None:
        assert self.ws is not None
        await self.ws.send(json.dumps(default_session_config(self.student_name, self.voice, self.level)))

    async def send_audio_chunk(self, pcm16_bytes: bytes) -> None:
        """Envia um pedaço de áudio (PCM16, 16kHz mono) capturado do microfone do aluno."""
        assert self.ws is not None
        b64 = base64.b64encode(pcm16_bytes).decode("ascii")
        await self.ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": b64,
        }))

    async def commit_audio(self) -> None:
        """Sinaliza fim do turno de fala do aluno (se o VAD automático não cobrir o caso)."""
        assert self.ws is not None
        await self.ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

    async def send_text_message(self, text: str) -> None:
        """Permite ao aluno digitar em vez de falar (fallback de acessibilidade)."""
        assert self.ws is not None
        item_id = f"msg_{uuid.uuid4().hex[:12]}"
        await self.ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "id": item_id,
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            },
        }))
        await self.ws.send(json.dumps({"type": "response.create"}))

    async def submit_tool_output(self, call_id: str, output: dict) -> None:
        """
        Necessário pelo protocolo de function calling: depois que o modelo chama
        'report_speech_analysis', devolvemos um ack para ele poder prosseguir com a
        resposta falada. Não precisamos de lógica real aqui (a análise já foi
        capturada pelo backend), só confirmar a chamada.
        """
        assert self.ws is not None
        await self.ws.send(json.dumps({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(output),
            },
        }))
        await self.ws.send(json.dumps({"type": "response.create"}))

    async def events(self) -> AsyncIterator[VoiceLiveEvent]:
        assert self.ws is not None
        try:
            async for raw in self.ws:
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                yield VoiceLiveEvent(type=data.get("type", "unknown"), raw=data)
        except websockets.ConnectionClosed:
            logger.info("Conexão Voice Live encerrada (aluno=%s)", self.student_name)
            return

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.ws is not None:
            await self.ws.close()


async def voicelive_text_completion(prompt: str, system: str | None = None) -> str:
    """
    Chamada pontual (não streaming de áudio) ao mesmo recurso/modelo, usada para
    tarefas de texto simples como tradução -- sem precisar de outra credencial/API.
    Abre uma sessão só-texto, manda uma mensagem, espera 'response.done', fecha.
    """
    session = VoiceLiveSession(student_name="system")
    await session.connect()
    assert session.ws is not None
    await session.ws.send(json.dumps({
        "type": "session.update",
        "session": {
            "modalities": ["text"],
            "model": cfg.VOICELIVE_MODEL,
            "instructions": system or "Você é um assistente de tradução conciso.",
        },
    }))
    await session.send_text_message(prompt)

    result_text = ""
    try:
        async for event in session.events():
            if event.type == "response.text.delta":
                result_text += event.raw.get("delta", "")
            elif event.type in ("response.done", "response.output_item.done"):
                if event.type == "response.done":
                    break
    finally:
        await session.close()

    return result_text.strip()
