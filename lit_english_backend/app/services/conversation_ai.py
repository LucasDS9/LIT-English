"""
"Cérebro" de texto da Conversa com IA Tutor.

Recebe a transcrição do que o aluno falou (já feita por
`app.routers.pronunciation.transcribe`, via Azure Speech com fallback para
Whisper local) e devolve, numa ÚNICA chamada de IA:

  1. a análise gramatical da fala do aluno (erros, frase corrigida, feedback
     em português), e
  2. a resposta do tutor que dá continuidade à conversa em inglês.

Por quê uma chamada de TEXTO separada, em vez de pedir tudo isso ao mesmo
modelo de voz em tempo real (como era feito antes, via function-calling
dentro da sessão Voice Live)? Porque um modelo de voz em streaming decidindo
"ao vivo" se deve chamar uma função e o que colocar nela é muito menos
confiável do que uma chamada de texto dedicada, em modo JSON, com um prompt
focado só nisso -- na prática, o modelo de voz frequentemente devolvia
`errors: []` mesmo quando a fala tinha erro claro. Esse módulo usa o MESMO
padrão (Groq, `response_format: json_object`) já comprovado em
`app/ai_judge.py` e `app/flashcard_judge.py`.

Requer a variável de ambiente GROQ_API_KEY (a mesma já usada pelos outros
corretores da plataforma).
"""

from __future__ import annotations

import json
import logging
import os
import time

import requests

logger = logging.getLogger("lit.conversation_ai")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# Erros de rede/timeout/5xx costumam ser passageiros -- vale tentar de novo
# antes de desistir (mesmo critério usado em ai_judge.py).
_MAX_RETRIES = 2

# Quantos turnos anteriores (aluno + tutor) mandar como contexto pra IA
# conseguir dar continuidade real à conversa, sem deixar o prompt gigante.
_MAX_HISTORY_TURNS = 12


class ConversationAiUnavailable(Exception):
    """A chamada à IA de conversa falhou (sem chave, rede, resposta inválida etc.)."""


def _system_prompt(
    student_name: str,
    level: str | None,
    target_language: str = "ingles",
    native_language: str = "pt",
) -> str:
    level_txt = f'O nível estimado do aluno é "{level}". ' if level else ""
    return f"""Você é o IA Tutor da plataforma LIT English, conversando por voz com o
aluno {student_name}. A língua-alvo que o aluno está praticando é {target_language}.
A língua nativa do aluno é {native_language}. {level_txt}

Você recebe o HISTÓRICO da conversa (se houver) e a ÚLTIMA fala do aluno, já transcrita por
reconhecimento de voz. A transcrição pode ter pequenas falhas de pontuação/capitalização,
que não devem ser tratadas como erros do aluno.

Sua tarefa tem duas partes:

1) ANÁLISE GRAMATICAL da fala do aluno (campo "errors"):
   - Procure ativamente erros reais de gramática na língua-alvo.
   - Cada erro deve conter wrong_fragment, correct_fragment e uma explicação curta em {native_language}.
   - Não invente erros, mas também não ignore erros reais.
   - "corrected_sentence": a frase inteira corrigida na língua-alvo. Se não houver erro, repita a original.
   - "feedback_native": uma frase curta e encorajadora na língua nativa do aluno.

2) CONTINUAÇÃO DA CONVERSA (campo "tutor_reply"):
   - Responda EXCLUSIVAMENTE na língua-alvo {target_language}.
   - Seja natural, curto, gentil e adequado ao nível do aluno.
   - Não repita a correção gramatical em voz alta.
   - Continue o assunto trazido pelo aluno e faça uma pergunta de acompanhamento quando fizer sentido.

Se a fala estiver vazia ou incompreensível, deixe errors vazio, escreva feedback_native na língua nativa
e peça gentilmente para o aluno repetir em {target_language}.

Responda APENAS com JSON válido, no formato exato:
{{
  "errors": [{{"wrong_fragment": "...", "correct_fragment": "...", "explanation_native": "..."}}],
  "corrected_sentence": "...",
  "feedback_native": "...",
  "tutor_reply": "..."
}}"""


def _build_messages(
    student_name: str,
    level: str | None,
    history: list[dict],
    student_text: str,
    target_language: str = "ingles",
    native_language: str = "pt",
) -> list[dict]:
    messages = [{"role": "system", "content": _system_prompt(student_name, level, target_language, native_language)}]

    for turn in history[-_MAX_HISTORY_TURNS:]:
        role = "assistant" if turn.get("role") == "tutor" else "user"
        text = (turn.get("text") or "").strip()
        if text:
            messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": student_text})
    return messages


def _call_groq(messages: list[dict]) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ConversationAiUnavailable("GROQ_API_KEY não configurada.")

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 700,
        "response_format": {"type": "json_object"},
    }

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=25,
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            errors_raw = parsed.get("errors") or []
            errors = [
                {
                    "wrong_fragment": str(e.get("wrong_fragment", "")),
                    "correct_fragment": str(e.get("correct_fragment", "")),
                    "explanation_native": str(
                        e.get("explanation_native", e.get("explanation_pt_br", ""))
                    ),
                }
                for e in errors_raw
                if isinstance(e, dict) and e.get("wrong_fragment")
            ]

            tutor_reply = str(parsed.get("tutor_reply", "")).strip()
            if not tutor_reply:
                raise ValueError("Resposta da IA sem o campo 'tutor_reply'.")

            feedback_native = str(
                parsed.get("feedback_native", parsed.get("feedback_pt_br", ""))
            ).strip()
            return {
                "errors": errors,
                "corrected_sentence": str(parsed.get("corrected_sentence", "")).strip(),
                "feedback_native": feedback_native,
                # Compatibility with older frontend/backend consumers.
                "feedback_pt_br": feedback_native,
                "tutor_reply": tutor_reply,
            }
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                logger.info("Tentativa %d da Conversa IA falhou, tentando de novo: %s", attempt + 1, e)
                time.sleep(0.6)
                continue

    raise ConversationAiUnavailable(f"Falha ao consultar a API da Groq: {last_error}") from last_error


def get_tutor_turn(
    student_name: str,
    student_text: str,
    history: list[dict],
    level: str | None = None,
    target_language: str = "ingles",
    native_language: str = "pt",
) -> dict:
    """
    Ponto de entrada usado pelo router.

    `history`: lista de dicts [{"role": "student"|"tutor", "text": "..."}]
    em ordem cronológica (mais antigo primeiro), SEM incluir a fala atual do
    aluno -- essa vai em `student_text`.

    Retorna:
      {"errors": [...], "corrected_sentence": str, "feedback_native": str, "tutor_reply": str}

    Levanta ConversationAiUnavailable se a IA não puder ser consultada -- o
    chamador (router) decide como avisar o aluno (não inventamos aqui uma
    análise falsa de "sem erros" só pra não travar, como acontecia antes).
    """
    student_text = (student_text or "").strip()
    messages = _build_messages(
        student_name, level, history, student_text, target_language, native_language
    )
    return _call_groq(messages)
