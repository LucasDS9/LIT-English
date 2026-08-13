"""
Consulta de vocabulário (dicionário contextual) — LIT English

Usado por app/routers/texts.py quando o aluno clica numa palavra dentro de um
texto de Read and Listen. Dado a palavra clicada e a frase onde ela aparece,
devolve:
  - a tradução da palavra para português (no sentido em que ela é usada
    naquela frase — não uma tradução genérica de dicionário);
  - uma frase de exemplo nova em inglês usando a palavra (diferente da frase
    original do texto, pra reforçar o vocabulário com um contexto extra);
  - a tradução dessa frase de exemplo para português.

Esse conteúdo é exatamente o que alimenta o popup de clique em palavra e o
botão "Salvar frase nos flashcards" (front = frase em inglês, back = frase em
português) — mas a decisão de salvar/exibir é do frontend; este módulo só
gera o conteúdo.

Usa a API da Groq (mesmo padrão de app/ai_judge.py). Requer a variável de
ambiente GROQ_API_KEY (carregada via .env por app/database.py).

Diferente do ai_judge, aqui NÃO existe fallback determinístico possível
(tradução não é algo que se possa "comparar exatamente") — se a API falhar,
o chamador deve tratar o erro e avisar o aluno para tentar de novo.
"""
import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Mesma lógica de retry do ai_judge: só tenta de novo em erro de rede/timeout/5xx,
# não em resposta mal formada (isso é problema de prompt, não de rede).
_MAX_RETRIES = 1

_SYSTEM_PROMPT = """Você é um assistente de vocabulário para alunos brasileiros aprendendo inglês.
Você recebe:
- "word": uma palavra (ou expressão curta) em inglês, clicada pelo aluno dentro de um texto.
- "sentence": a frase COMPLETA do texto onde essa palavra aparece — este é o contexto principal.
- "context_before" (opcional): ~3 palavras imediatamente antes de "word" dentro de "sentence".
- "context_after" (opcional): ~3 palavras imediatamente depois de "word" dentro de "sentence".

Use "sentence" como fonte primária para determinar o sentido. "context_before" e "context_after"
são apoio adicional — NÃO os substituam pela frase inteira.

Exemplos:
- sentence "I need to book a room for tomorrow." + word "book" → translation "reservar" (NÃO "livro").
- sentence "I read an interesting book yesterday." + word "book" → translation "livro".

Sua tarefa é devolver, em JSON, exatamente estes campos:
- "translation": a tradução de "word" para português, no sentido em que ela é usada em
  "sentence" (não uma lista de significados — apenas a tradução certa para esse contexto).
  Se um único sentido claramente se encaixa, devolva só esse. Minúsculas, sem artigo, a não ser
  que o artigo seja parte do sentido (ex.: "the" -> "o/a").
- "example_en": UMA frase nova e natural em inglês, DIFERENTE de "sentence", usando "word"
  (pode flexionar a palavra — plural, tempo verbal, etc. — se necessário para a frase ficar
  natural). A frase deve ser simples, curta (até ~12 palavras) e apropriada para estudante
  de inglês (sem gírias obscuras, sem conteúdo sensível). A palavra ou sua forma flexionada
  deve aparecer claramente na frase.
- "example_pt": a tradução de "example_en" para português, natural (não literal palavra por
  palavra).

Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, no formato exato:
{"translation": "...", "example_en": "...", "example_pt": "..."}
"""


class VocabLookupUnavailable(Exception):
    """Erro ao consultar a API de vocabulário (sem chave, rede, resposta inválida etc.)."""


def _call_groq(
    word: str,
    sentence: str,
    context_before: str | None = None,
    context_after: str | None = None,
) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise VocabLookupUnavailable("GROQ_API_KEY não configurada.")

    user_payload: dict[str, str] = {"word": word, "sentence": sentence}
    if context_before:
        user_payload["context_before"] = context_before
    if context_after:
        user_payload["context_after"] = context_after

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.4,
        "max_tokens": 300,
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
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            for field in ("translation", "example_en", "example_pt"):
                if not parsed.get(field):
                    raise ValueError(f"Resposta da IA sem o campo '{field}'.")

            return {
                "translation": str(parsed["translation"]).strip(),
                "example_en": str(parsed["example_en"]).strip(),
                "example_pt": str(parsed["example_pt"]).strip(),
            }
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                logger.info(
                    "Tentativa %d de lookup de vocabulário falhou, tentando de novo: %s",
                    attempt + 1,
                    e,
                )
                time.sleep(0.5)
                continue
    raise VocabLookupUnavailable(f"Falha ao consultar a API da Groq: {last_error}") from last_error


def lookup_word(
    word: str,
    sentence: str,
    context_before: str | None = None,
    context_after: str | None = None,
) -> dict:
    """
    Consulta a tradução contextual de `word` (dado `sentence` como contexto)
    e gera uma frase de exemplo nova em inglês + sua tradução.

    Retorna {"word": str, "translation": str, "example_en": str, "example_pt": str}.

    Levanta VocabLookupUnavailable se a API da Groq não puder ser consultada
    (sem chave, rede fora, resposta inválida após retries) — o chamador
    (router) deve converter isso em um HTTP 503 para o frontend.
    """
    word_clean = (word or "").strip()
    sentence_clean = (sentence or "").strip()

    if not word_clean:
        raise ValueError("Palavra vazia.")

    result = _call_groq(
        word_clean,
        sentence_clean,
        (context_before or "").strip() or None,
        (context_after or "").strip() or None,
    )
    return {
        "word": word_clean,
        "translation": result["translation"],
        "example_en": result["example_en"],
        "example_pt": result["example_pt"],
    }
