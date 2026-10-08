"""
Geração automática de palavras do "Aprender" via Groq.

Quando a fila de palavras novas de um aluno está acabando, o backend pede à
Groq um lote de palavras novas e só aceita o que respeitar as MESMAS regras do
cadastro manual (routers/vocab_words.py):

  - palavra na língua-alvo do aluno (ingles / italiano / frances);
  - tradução em português do Brasil;
  - exatamente 3 distratores (também em português), todos diferentes da
    tradução correta e diferentes entre si -> sempre 4 opções;
  - 3 frases de exemplo na língua-alvo, que contenham a palavra;
  - nível CEFR (A1..B2);
  - sem repetir palavras que o aluno já tem.

Itens fora das regras são descartados (nunca vão pro aluno). Requer
GROQ_API_KEY (mesma variável usada pelo resto da plataforma).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

LEVELS = ["A1", "A2", "B1", "B2"]
ALLOWED_POS = {"noun", "verb", "adjective", "adverb", "expression", "preposition", "pronoun"}

_LANGUAGE_NAMES = {"ingles": "inglês", "italiano": "italiano", "frances": "francês"}
_MAX_RETRIES = 1

_SYSTEM_PROMPT = """Você cria vocabulário para um app de aprendizado de idiomas usado por brasileiros.
Você recebe um JSON com:
- "target_language": a língua que o aluno estuda.
- "level": nível CEFR das palavras (A1, A2, B1 ou B2).
- "count": quantas palavras gerar.
- "already_known": palavras que o aluno JÁ tem — NÃO repita nenhuma delas.

Gere "count" palavras ou expressões curtas MUITO comuns e úteis para esse nível, variando
as classes gramaticais (substantivos, verbos, adjetivos, expressões...). Nada de gírias
obscuras, palavrões ou conteúdo sensível.

Para cada palavra devolva:
- "word": a palavra na língua-alvo (verbos no infinitivo; em inglês, sem "to").
- "part_of_speech": um destes valores: noun, verb, adjective, adverb, expression, preposition, pronoun.
- "translation": tradução em português do Brasil, minúscula, curta, sem artigo.
- "distractors": EXATAMENTE 3 traduções erradas em português do Brasil. Devem ser da mesma
  classe gramatical, plausíveis (não absurdas), diferentes entre si e diferentes de "translation".
  Nenhuma pode ser sinônimo aceitável de "translation".
- "example_sentences": EXATAMENTE 3 frases curtas e naturais (até ~12 palavras) na língua-alvo,
  cada uma contendo a palavra (pode estar flexionada).
- "level": o nível CEFR da palavra.

Responda APENAS com JSON válido, sem texto antes ou depois, no formato:
{"words": [{"word": "...", "part_of_speech": "...", "translation": "...", "distractors": ["...","...","..."], "example_sentences": ["...","...","..."], "level": "A1"}]}
"""


class VocabGenerationUnavailable(Exception):
    """Groq indisponível (sem chave, rede, resposta inválida)."""


@dataclass(frozen=True)
class GeneratedWord:
    word: str
    part_of_speech: str
    translation: str
    example_sentence: str
    example_sentences: tuple[str, str, str]
    distractors: tuple[str, str, str]
    level: str


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _validate_item(item: dict, level: str, known: set[str]) -> GeneratedWord | None:
    """Aplica as regras do Aprender. Devolve None se o item não servir."""
    try:
        word = str(item["word"]).strip()
        pos = str(item["part_of_speech"]).strip().lower()
        translation = str(item["translation"]).strip().lower()
        distractors = [str(d).strip().lower() for d in item["distractors"]]
        sentences = [str(s).strip() for s in item["example_sentences"]]
    except (KeyError, TypeError):
        return None

    if not word or not translation or _norm(word) in known:
        return None
    if pos not in ALLOWED_POS:
        return None
    # Sempre 4 opções distintas: 3 distratores, nenhum igual à tradução.
    if len(distractors) != 3 or any(not d for d in distractors):
        return None
    options = {translation, *distractors}
    if len(options) != 4:
        return None
    # 3 frases de exemplo, e a palavra tem que aparecer em pelo menos uma
    # (a palavra pode vir flexionada, então comparamos pelo radical).
    if len(sentences) != 3 or any(not s for s in sentences):
        return None
    stem = _norm(word)
    stem = stem[: max(3, len(stem) - 2)] if " " not in stem else stem
    if not any(stem in _norm(s) for s in sentences):
        return None

    item_level = str(item.get("level") or level).strip().upper()
    if item_level not in LEVELS:
        item_level = level

    return GeneratedWord(
        word=word,
        part_of_speech=pos,
        translation=translation,
        example_sentence=sentences[0],
        example_sentences=(sentences[0], sentences[1], sentences[2]),
        distractors=(distractors[0], distractors[1], distractors[2]),
        level=item_level,
    )


def generate_words(
    language: str,
    level: str,
    count: int,
    already_known: list[str],
) -> list[GeneratedWord]:
    """Pede `count` palavras novas à Groq e devolve só as que passam nas regras."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise VocabGenerationUnavailable("GROQ_API_KEY não configurada.")

    language = (language or "ingles").strip().lower()
    level = level if level in LEVELS else "A1"
    known = {_norm(w) for w in already_known}

    user_payload = {
        "target_language": _LANGUAGE_NAMES.get(language, language),
        "level": level,
        # Pedimos um pouco a mais porque alguns itens podem ser descartados.
        "count": count + 2,
        # Limita o tamanho do prompt: só as palavras mais recentes.
        "already_known": sorted(known)[-300:],
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.7,
        "reasoning_effort": "low",
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = requests.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            raw_items = json.loads(content).get("words", [])
            if not isinstance(raw_items, list):
                raise ValueError("Campo 'words' não é uma lista.")

            result: list[GeneratedWord] = []
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                gw = _validate_item(raw, level, known)
                if gw:
                    known.add(_norm(gw.word))  # evita duplicata dentro do próprio lote
                    result.append(gw)
            if not result:
                raise ValueError("Nenhuma palavra válida no lote gerado.")
            return result[:count]
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                logger.info("Geração de vocabulário falhou (tentativa %d): %s", attempt + 1, exc)
                time.sleep(0.5)
    raise VocabGenerationUnavailable(f"Falha ao gerar palavras via Groq: {last_error}") from last_error
