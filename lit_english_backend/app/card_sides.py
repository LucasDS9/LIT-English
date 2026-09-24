"""
Orientação frente/verso dos flashcards.

Convenção do sistema: `front` = língua-alvo, `back` = língua nativa. Mas há
cards que chegam invertidos (ex.: criados à mão pelo professor ou pelo aluno
com os dois lados preenchidos, sem passar pela detecção da IA). Para os
exercícios "língua nativa -> língua-alvo" (digitar e falar) isso importa:
mostrar o lado errado entrega a resposta.

`orient_card` devolve (texto_na_língua_alvo, texto_na_língua_nativa). Quem
decide é a IA (`orient_flashcard_sides`): ela identifica o lado em cada língua,
inverte se estiverem trocados e traduz o que faltar (ex.: verso vazio). O
resultado fica em cache na memória do servidor (um card só consulta a IA uma
vez). Se a IA estiver indisponível, cai numa detecção offline por palavras
funcionais, que só inverte com evidência clara e, na dúvida, mantém a
convenção front = alvo.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import re

from app.ai_translate import TranslationUnavailable, orient_flashcard_sides

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "pt": (
        "o os as um uma uns umas de do da dos das em no na nos nas para pra por com sem "
        "que não nao é eu você voce ele ela nós eles elas meu minha seu sua isso isto "
        "esse essa este esta muito mais mas ou também tambem quando onde como está estou "
        "tem têm foi são sou ser estar fazer quer quero pessoa"
    ),
    "en": (
        "the a an of to in on at for with and or but is are was were be been am i you he "
        "she it we they my your his her its our their this that these those do does did "
        "not no have has had will would can could there here what who how why when where "
        "me him them us to from by about also very"
    ),
    "it": (
        "il lo la i gli le un uno una di del della dei delle dello degli in nel nella nei "
        "nelle su sul sulla per con senza che non è sono io tu lui lei noi voi loro mio "
        "mia tuo tua suo sua questo questa quello quella molto più ma o anche quando dove "
        "come ho hai ha abbiamo hanno era erano c ci vuole vuoi voglio fare niente nulla"
    ),
    "fr": (
        "le la les un une des du de en dans sur pour avec sans que qui ne pas est sont "
        "je tu il elle nous vous ils elles mon ma mes ton ta tes son sa ses ce cette ces "
        "très plus mais ou aussi quand où comment suis es a ai as avons avez ont était "
        "être avoir faire veux veut rien"
    ),
}

_LANG_CODE = {
    "ingles": "en", "inglês": "en", "en": "en", "english": "en",
    "italiano": "it", "it": "it",
    "frances": "fr", "francês": "fr", "fr": "fr",
    "portugues": "pt", "português": "pt", "pt": "pt", "pt-br": "pt",
}

_WORD_RE = re.compile(r"[a-zà-ÿ]+", re.IGNORECASE)


def _code(lang: str | None) -> str | None:
    return _LANG_CODE.get((lang or "").strip().lower())


def _lean(text: str, target: str, native: str) -> int:
    """> 0: parece língua-alvo; < 0: parece língua nativa; 0: sem evidência."""
    target_words = set(_STOPWORDS[target].split())
    native_words = set(_STOPWORDS[native].split())
    only_target = target_words - native_words
    only_native = native_words - target_words

    score = 0
    for token in _WORD_RE.findall((text or "").lower()):
        if token in only_target:
            score += 1
        elif token in only_native:
            score -= 1

    # Sinais de escrita exclusivos do português frente a it/fr/en.
    if native == "pt" and target != "pt":
        if re.search(r"[ãõ]", (text or "").lower()):
            score -= 1
        if target != "fr" and "ç" in (text or "").lower():
            score -= 1
    return score


def _orient_by_heuristic(front: str, back: str, target_language: str, native_language: str = "pt") -> tuple[str, str]:
    """Fallback offline: (texto na língua-alvo, texto na língua nativa)."""
    target = _code(target_language)
    native = _code(native_language) or "pt"
    if target not in _STOPWORDS or native not in _STOPWORDS or target == native:
        return front, back

    front_lean = _lean(front, target, native)
    back_lean = _lean(back, target, native)

    # Só inverte com evidência clara: o verso parece bem mais "alvo" que a frente.
    if back_lean - front_lean >= 2 and back_lean > 0:
        return back, front
    return front, back


_CACHE: dict[tuple, tuple[str, str]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 5000


def orient_card(front: str, back: str, target_language: str, native_language: str = "pt") -> tuple[str, str]:
    """Retorna (texto na língua-alvo, texto na língua nativa), usando a IA (com cache)."""
    front = front or ""
    back = back or ""
    key = (front, back, (target_language or "").lower(), (native_language or "pt").lower())

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached:
        return cached

    try:
        result = orient_flashcard_sides(front, back, native_language or "pt", target_language)
    except TranslationUnavailable:
        # Não guarda no cache: na próxima vez tenta a IA de novo.
        return _orient_by_heuristic(front, back, target_language, native_language)
    except Exception:  # noqa: BLE001 — orientar nunca pode derrubar a revisão
        logger.exception("Falha inesperada ao orientar flashcard; usando detecção offline.")
        return _orient_by_heuristic(front, back, target_language, native_language)

    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = result
    return result


def orient_many(items, target_language: str, native_language: str = "pt", max_workers: int = 6) -> dict:
    """Orienta vários cards em paralelo. `items`: iterável de (id, front, back). Retorna {id: (alvo, nativo)}."""
    items = list(items)
    if not items:
        return {}
    workers = max(1, min(max_workers, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda it: orient_card(it[1], it[2], target_language, native_language), items
        ))
    return {it[0]: res for it, res in zip(items, results)}
