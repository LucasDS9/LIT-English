"""
Tradução automática de flashcards — LIT English

Usado por app/routers/flashcards.py (rota /flashcards/self-add) quando o
aluno cria um flashcard próprio e deixa o campo "Verso" em branco: a frente
pode estar na língua nativa ou na língua-alvo, e a Groq gera automaticamente
a tradução para a outra língua.

Requer a variável de ambiente GROQ_API_KEY (carregada via .env por
app/database.py). Se a API falhar por qualquer motivo (sem chave, rede
fora, resposta inesperada), levanta TranslationUnavailable — quem chamar
decide o que fazer (hoje: devolve erro pro aluno pedindo pra preencher o
verso manualmente, já que "inventar" uma tradução errada seria pior do que
pedir pro aluno completar).
"""
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# Mesmo espírito do TTS_LANGUAGE_CODES em app/routers/tts.py: mapa língua-alvo
# (campo `language`/`target_language` do app) -> nome por extenso em
# português, usado só pra montar o prompt da IA.
LANGUAGE_NAMES = {
    "ingles": "inglês",
    "italiano": "italiano",
    "frances": "francês",
}
DEFAULT_LANGUAGE_NAME = "inglês"

_SYSTEM_PROMPT = (
    "Você é um tradutor para alunos brasileiros de idiomas. Você recebe um termo ou "
    "frase em {source_language} e devolve a tradução para o português do Brasil, "
    "natural e direta — sem explicações, sem aspas, sem alternativas entre parênteses. "
    "Se o texto recebido tiver mais de uma palavra, traduza a frase inteira mantendo o "
    "sentido, não palavra por palavra. "
    'Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, no formato '
    'exato: {{"translation": "tradução aqui"}}'
)


class TranslationUnavailable(Exception):
    """Erro ao chamar a API de tradução (sem chave, rede, resposta inválida etc.)."""


def translate_to_portuguese(text: str, source_language: str) -> str:
    """
    Traduz `text` (na língua-alvo do aluno, ex.: "ingles"/"italiano") para
    português do Brasil. Levanta TranslationUnavailable se a IA não puder
    ser consultada ou devolver algo inválido.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Texto vazio.")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise TranslationUnavailable("GROQ_API_KEY não configurada.")

    language_name = LANGUAGE_NAMES.get((source_language or "").strip().lower(), DEFAULT_LANGUAGE_NAME)

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT.format(source_language=language_name)},
            {"role": "user", "content": clean_text},
        ],
        "temperature": 0.2,
        "reasoning_effort": "low",
        "max_tokens": 150,
        "response_format": {"type": "json_object"},
    }

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
        translation = str(parsed.get("translation", "")).strip()
        if not translation:
            raise ValueError("Tradução vazia devolvida pela IA.")
        return translation
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
        logger.warning("Tradução automática indisponível: %s", e)
        raise TranslationUnavailable(f"Falha ao consultar a API da Groq: {e}") from e


# ---------------------------------------------------------------------------
# Flashcard livre: a frente pode estar na língua nativa OU na língua-alvo.
# Nesse caso, o verso automático deve ser a outra língua.
# ---------------------------------------------------------------------------

_LANGUAGE_NAMES = {
    "pt": "português",
    "pt-br": "português",
    "portugues": "português",
    "português": "português",
    "ingles": "inglês",
    "inglês": "inglês",
    "en": "inglês",
    "italiano": "italiano",
    "it": "italiano",
    "frances": "francês",
    "francês": "francês",
    "fr": "francês",
}

_BIDIRECTIONAL_PROMPT = (
    "Você é um tradutor para estudantes de idiomas. O aluno está criando um flashcard. "
    "A língua nativa é {native_language} e a língua-alvo é {target_language}. "
    "A frase/expressão recebida pode estar em qualquer uma dessas duas línguas. "
    "Identifique qual é a língua do texto e traduza naturalmente para a OUTRA língua. "
    "Preserve o sentido completo da expressão, sem explicações, sem aspas e sem alternativas. "
    'Responda APENAS com um JSON válido no formato exato: '
    '{{"translation": "tradução aqui", "detected_language": "idioma detectado"}}'
)


def translate_flashcard_front(text: str, native_language: str, target_language: str) -> str:
    """
    Detecta se a frente está na língua nativa ou na língua-alvo e traduz para a outra.
    Usada somente quando o aluno deixa o verso vazio.
    """
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("Texto vazio.")

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise TranslationUnavailable("GROQ_API_KEY não configurada.")

    native_name = _LANGUAGE_NAMES.get((native_language or "").strip().lower(), "português")
    target_name = _LANGUAGE_NAMES.get((target_language or "").strip().lower(), "inglês")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": _BIDIRECTIONAL_PROMPT.format(
                    native_language=native_name,
                    target_language=target_name,
                ),
            },
            {"role": "user", "content": clean_text},
        ],
        "temperature": 0.2,
        "reasoning_effort": "low",
        "max_tokens": 180,
        "response_format": {"type": "json_object"},
    }

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
        translation = str(parsed.get("translation", "")).strip()
        detected = str(parsed.get("detected_language", "")).strip().lower()
        allowed = {native_name.lower(), target_name.lower()}

        if not translation:
            raise ValueError("Tradução vazia devolvida pela IA.")
        if detected and detected not in allowed:
            raise ValueError("A IA detectou uma língua diferente das línguas do aluno.")

        return translation
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
        logger.warning("Tradução bidirecional indisponível: %s", e)
        raise TranslationUnavailable(f"Falha ao consultar a API da Groq: {e}") from e
