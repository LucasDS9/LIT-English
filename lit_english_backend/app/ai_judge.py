"""
Julgamento semântico de respostas de exercícios — LIT English

Usado por app/routers/exercises.py para decidir se a resposta do aluno está
certa (seja ela digitada — "Fill in the blank" e "Listen and type" — ou
falada e transcrita pelo Faster-Whisper — "Speak it!"), SEM exigir que seja
idêntica, palavra por palavra, à resposta esperada.

Critério de "certo aaa":
  1. A resposta do aluno é gramaticalmente correta em inglês (no contexto da
     frase, quando aplicável).
  2. A resposta do aluno tem o MESMO SENTIDO da resposta esperada (paráfrases
     e sinônimos que preservam o significado contam como certo; respostas que
     mudam o sentido, mesmo que gramaticalmente corretas, contam como erro).

Além de dizer se está certo ou errado, a IA sempre devolve um `reason`
(explicação curta, em português) — especialmente útil quando a resposta
está errada, pra o aluno entender o que corrigir.

Usa a API da Groq (compatível com o formato de chat completions da OpenAI).
Requer a variável de ambiente GROQ_API_KEY (carregada via .env por
app/database.py, que já roda load_dotenv() no import da aplicação).

Se a API falhar por qualquer motivo (sem chave, rede fora, resposta
inesperada), cai de volta para comparação exata (determinística), para o
exercício nunca travar por causa de um problema externo. Nesse caso o
`reason` explica que foi usada a comparação exata (IA indisponível).
"""
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

_SYSTEM_PROMPT = """Você é um corretor de exercícios de inglês para alunos brasileiros. Você
recebe:
- "expected": a resposta que o aluno deveria dar.
- "given": o que o aluno realmente respondeu (pode ter vindo de texto digitado ou de
  transcrição por reconhecimento de voz).
- "context" (pode vir vazio): a frase completa em que a resposta se encaixa, útil quando
  "expected"/"given" são só uma palavra ou trecho de uma lacuna a preencher.

Decida se a resposta do aluno está CORRETA. Ela está correta se, E SOMENTE SE, as duas
condições abaixo forem verdadeiras:
1. A resposta "given" é gramaticalmente válida em inglês nesse contexto (aceite pequenas
   imperfeições típicas de fala transcrita ou digitação rápida, como pontuação ou
   capitalização ausente, mas erros reais de gramática — concordância verbal, tempo verbal
   errado, artigo/preposição errada, palavra da classe gramatical errada, etc. — tornam a
   resposta incorreta).
2. A resposta "given" tem o MESMO SIGNIFICADO da resposta "expected". Paráfrases, sinônimos
   e outras formas de dizer a mesma coisa contam como corretas (ex.: "I like reading books"
   e "I like to read" têm o mesmo sentido). Respostas que mudam o sentido, invertem, negam,
   trocam por uma palavra de sentido diferente (ex.: "read" por "write"), ou dizem algo
   diferente do que foi pedido são incorretas, mesmo que gramaticalmente perfeitas.

Se a resposta do aluno estiver vazia, incompreensível, ou não fizer sentido nenhum em
inglês, marque como incorreta.

Sempre explique sua decisão em "reason", em português, numa frase curta e direta (o aluno
vai ler essa explicação). Quando a resposta estiver ERRADA, a explicação precisa dizer
CLARAMENTE o que está errado (ex.: erro de gramática específico, ou que o sentido mudou e
por quê) — isso é o mais importante da sua resposta. Quando estiver CORRETA, uma frase
curta confirmando por que também é uma forma válida já basta.

Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, no formato exato:
{"correct": true ou false, "reason": "explicação curta em português"}
"""


class AiJudgeUnavailable(Exception):
    """Erro ao chamar a API de julgamento (sem chave, rede, resposta inválida etc.)."""


def _call_groq(expected: str, given: str, context: str | None) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise AiJudgeUnavailable("GROQ_API_KEY não configurada.")

    user_payload = {"expected": expected, "given": given, "context": context or ""}

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "temperature": 0.2,
        "max_tokens": 250,
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
        if "correct" not in parsed:
            raise ValueError("Resposta da IA sem o campo 'correct'.")
        return {
            "correct": bool(parsed["correct"]),
            "reason": str(parsed.get("reason", "")),
        }
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
        raise AiJudgeUnavailable(f"Falha ao consultar a API da Groq: {e}") from e


def judge_answer(expected: str, given: str, context: str | None = None) -> dict:
    """
    Julga se `given` (resposta do aluno — digitada ou transcrita) está
    correto em relação a `expected` (resposta esperada), de forma
    não-determinística (semântica + gramatical), usando a Groq.

    `context`, quando informado, é a frase completa em que a resposta se
    encaixa (útil para exercícios de lacuna, onde expected/given são só uma
    palavra ou trecho curto) — ajuda a IA a julgar concordância/tempo verbal
    corretamente.

    Retorna {"correct": bool, "reason": str, "ai_used": bool}.
    Em caso de falha da API, cai para comparação exata normalizada e marca
    "ai_used": False (para o chamador saber que foi o modo de contingência).
    """
    given_clean = (given or "").strip()

    if not given_clean:
        return {"correct": False, "reason": "Resposta vazia ou não reconhecida.", "ai_used": True}

    try:
        result = _call_groq(expected, given_clean, context)
        return {"correct": result["correct"], "reason": result["reason"], "ai_used": True}
    except AiJudgeUnavailable as e:
        logger.warning("Julgamento por IA indisponível, usando comparação exata: %s", e)
        fallback_correct = _normalize(expected) == _normalize(given_clean)
        reason = (
            "Resposta idêntica à esperada (IA indisponível no momento, comparação exata usada)."
            if fallback_correct
            else "Resposta diferente da esperada (IA indisponível no momento, comparação exata usada)."
        )
        return {"correct": fallback_correct, "reason": reason, "ai_used": False}


def _normalize(text: str) -> str:
    return text.strip().lower().rstrip(".,!?")
