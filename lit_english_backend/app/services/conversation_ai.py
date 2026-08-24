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


def _system_prompt(student_name: str, level: str | None) -> str:
    level_txt = f'O nível estimado do aluno é "{level}". ' if level else ""
    return f"""Você é o IA Tutor de inglês da plataforma LIT English, conversando por voz com o
aluno brasileiro {student_name}. {level_txt}

Você recebe o HISTÓRICO da conversa (se houver) e a ÚLTIMA fala do aluno, já transcrita por
reconhecimento de voz (pode ter pequenas falhas de pontuação/capitalização típicas de
transcrição -- isso NÃO é erro do aluno e não deve ser reportado).

Sua tarefa tem duas partes, sempre nessa ordem de importância:

1) ANÁLISE GRAMATICAL da fala do aluno (campo "errors"):
   - Releia a frase do aluno com atenção e procure ATIVAMENTE por erros reais de gramática:
     tempo verbal errado (ex.: presente no lugar de passado, "I buy" quando deveria ser
     "I bought"), concordância verbal (ex.: "she go" em vez de "she goes"), artigo errado ou
     faltando, preposição errada, ordem de palavras errada, escolha de palavra errada.
   - Cada erro encontrado vira um item em "errors" com: o trecho exato errado
     (wrong_fragment), a forma correta (correct_fragment), e uma explicação curta e clara em
     português do Brasil (explanation_pt_br).
   - NÃO invente erros que não existem, mas também NÃO deixe passar erros reais só para ser
     gentil -- isso prejudica o aprendizado do aluno. Se a frase tiver erro, "errors" JAMAIS
     deve vir vazio.
   - "corrected_sentence": a frase inteira do aluno reescrita corretamente em inglês. Se não
     houver nenhum erro, repita a frase original aqui.
   - "feedback_pt_br": 1 frase curta e encorajadora em português sobre a fala como um todo.

2) CONTINUAÇÃO DA CONVERSA (campo "tutor_reply"):
   - Responda ao aluno em INGLÊS (nunca em português), com uma frase curta e natural que dê
     continuidade à conversa -- comente o que ele disse e/ou faça uma pergunta de
     acompanhamento, adequada ao nível do aluno.
   - NÃO repita a correção gramatical em voz alta aqui (ela já aparece na tela separadamente).
   - Seja gentil, caloroso e encorajador -- é um ambiente de aprendizado.

Se a fala do aluno estiver vazia, incompreensível, ou não fizer sentido nenhum em inglês,
deixe "errors" vazio, explique isso em "feedback_pt_br", e em "tutor_reply" peça gentilmente
para ele repetir, em inglês simples.

Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, no formato exato:
{{
  "errors": [{{"wrong_fragment": "...", "correct_fragment": "...", "explanation_pt_br": "..."}}],
  "corrected_sentence": "...",
  "feedback_pt_br": "...",
  "tutor_reply": "..."
}}"""


def _build_messages(
    student_name: str,
    level: str | None,
    history: list[dict],
    student_text: str,
) -> list[dict]:
    messages = [{"role": "system", "content": _system_prompt(student_name, level)}]

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
                    "explanation_pt_br": str(e.get("explanation_pt_br", "")),
                }
                for e in errors_raw
                if isinstance(e, dict) and e.get("wrong_fragment")
            ]

            tutor_reply = str(parsed.get("tutor_reply", "")).strip()
            if not tutor_reply:
                raise ValueError("Resposta da IA sem o campo 'tutor_reply'.")

            return {
                "errors": errors,
                "corrected_sentence": str(parsed.get("corrected_sentence", "")).strip(),
                "feedback_pt_br": str(parsed.get("feedback_pt_br", "")).strip(),
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
) -> dict:
    """
    Ponto de entrada usado pelo router.

    `history`: lista de dicts [{"role": "student"|"tutor", "text": "..."}]
    em ordem cronológica (mais antigo primeiro), SEM incluir a fala atual do
    aluno -- essa vai em `student_text`.

    Retorna:
      {"errors": [...], "corrected_sentence": str, "feedback_pt_br": str, "tutor_reply": str}

    Levanta ConversationAiUnavailable se a IA não puder ser consultada -- o
    chamador (router) decide como avisar o aluno (não inventamos aqui uma
    análise falsa de "sem erros" só pra não travar, como acontecia antes).
    """
    student_text = (student_text or "").strip()
    messages = _build_messages(student_name, level, history, student_text)
    return _call_groq(messages)
