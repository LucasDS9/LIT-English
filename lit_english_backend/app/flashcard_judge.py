"""
Julgamento semântico de respostas de flashcards — francês e italiano.

Usado por app/routers/flashcards.py para TYPE_PT e TYPE_TARGET quando o aluno
estuda italiano ou francês. Complementa a normalização básica (mesma ideia do
inglês em ai_judge.py) com equivalência semântica via Groq.

Inglês continua com comparação simples (strip + lower) — este módulo não é
chamado para alunos do curso normal.
"""
import json
import logging
import os
import re
import time
import unicodedata

import requests

from app.ai_judge import AiJudgeUnavailable

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
_MAX_RETRIES = 1

_LANGUAGE_LABELS = {
    "português": "português",
    "portugues": "português",
    "italiano": "italiano",
    "frances": "francês",
    "francês": "francês",
    "ingles": "inglês",
    "inglês": "inglês",
}

_SYSTEM_PROMPT = """Você é um corretor de flashcards de idiomas para alunos brasileiros.

Recebe um JSON com:
- "expected": resposta esperada (referência correta).
- "given": resposta do aluno.
- "answer_language": idioma em que a resposta do aluno deveria estar (ex.: "português", "italiano", "francês").
- "target_language": língua-alvo do curso (ex.: "italiano", "francês").
- "context": frase original ou tradução de referência (pode estar vazio).

Decida se "given" é ACEITÁVEL em relação a "expected".

NÍVEL 1 — MUITO PARECIDO (aceitar):
- sinônimos e pequenas variações naturais;
- artigos, flexões que não alteram o sentido;
- pontuação, maiúsculas/minúsculas, espaços extras;
- pequenas diferenças de construção que um professor aceitaria.

NÍVEL 2 — EQUIVALÊNCIA SEMÂNTICA (aceitar):
- tradução ou paráfrase que transmite a MESMA mensagem de forma natural no idioma de "answer_language";
- palavras diferentes, mas mesmo significado prático para um falante nativo.

NÃO aceitar:
- respostas apenas relacionadas semanticamente, mas com significado diferente;
- traduções que omitam informação essencial;
- respostas em idioma errado;
- respostas vazias ou incompreensíveis.

Seja CONSERVADOR: em dúvida real, marque como incorreto.

Responda APENAS com JSON válido, sem texto extra:
{"correct": true ou false, "confidence": número entre 0 e 1, "reason": "explicação curta em português"}
"""


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_flashcard_answer(text: str) -> str:
    """
    Normalização básica antes da IA — mesma filosofia do inglês em ai_judge.py:
    minúsculas, sem pontuação, espaços colapsados. Também remove acentos para
    comparação determinística (ex.: " até " == "ate").
    """
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return _strip_accents(text)


def _language_label(code: str) -> str:
    return _LANGUAGE_LABELS.get((code or "").strip().lower(), code or "")


def _call_groq(payload: dict) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise AiJudgeUnavailable("GROQ_API_KEY não configurada.")

    request_payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "max_tokens": 250,
        "response_format": {"type": "json_object"},
    }

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            if "correct" not in parsed:
                raise ValueError("Resposta da IA sem o campo 'correct'.")
            confidence = parsed.get("confidence", 0.0)
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            return {
                "correct": bool(parsed["correct"]),
                "confidence": confidence,
                "reason": str(parsed.get("reason", "")),
            }
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                logger.info("Tentativa %d de julgamento de flashcard falhou, tentando de novo: %s", attempt + 1, exc)
                time.sleep(0.5)
                continue
    raise AiJudgeUnavailable(f"Falha ao consultar a API da Groq: {last_error}") from last_error


def judge_flashcard_answer(
    expected: str,
    given: str,
    *,
    target_language: str,
    answer_language: str,
    context: str | None = None,
) -> dict:
    """
    Julga equivalência semântica para flashcards de francês/italiano.

    Retorna {"correct": bool, "confidence": float, "reason": str, "ai_used": bool}.
    Em falha da IA, usa fallback seguro (comparação normalizada — nunca aceita
    automaticamente).
    """
    given_clean = (given or "").strip()
    if not given_clean:
        return {
            "correct": False,
            "confidence": 1.0,
            "reason": "Resposta vazia.",
            "ai_used": False,
        }

    if normalize_flashcard_answer(expected) == normalize_flashcard_answer(given_clean):
        return {
            "correct": True,
            "confidence": 1.0,
            "reason": "Resposta corresponde à esperada (diferenças de pontuação ou acentuação à parte).",
            "ai_used": False,
        }

    user_payload = {
        "expected": expected,
        "given": given_clean,
        "answer_language": _language_label(answer_language),
        "target_language": _language_label(target_language),
        "context": context or "",
    }

    try:
        result = _call_groq(user_payload)
        correct = result["correct"]
        reason = result["reason"]
        if not correct and normalize_flashcard_answer(expected) == normalize_flashcard_answer(given_clean):
            correct = True
            reason = "Resposta corresponde à esperada (diferenças de pontuação ou acentuação à parte)."
        return {
            "correct": correct,
            "confidence": result["confidence"],
            "reason": reason,
            "ai_used": True,
        }
    except AiJudgeUnavailable as exc:
        logger.warning("Julgamento por IA indisponível para flashcard, usando comparação normalizada: %s", exc)
        fallback_correct = normalize_flashcard_answer(expected) == normalize_flashcard_answer(given_clean)
        return {
            "correct": fallback_correct,
            "confidence": 1.0 if fallback_correct else 0.0,
            "reason": (
                "Resposta idêntica à esperada (IA indisponível, comparação exata usada)."
                if fallback_correct
                else "Resposta diferente da esperada (IA indisponível, comparação exata usada)."
            ),
            "ai_used": False,
        }
