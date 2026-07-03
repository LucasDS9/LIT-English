"""
Julgamento semântico de respostas de exercícios — LIT English

Usado por app/routers/exercises.py para decidir se a resposta do aluno está
certa (seja ela digitada — "Fill in the blank" e "Listen and type" — ou
falada e transcrita pelo Faster-Whisper — "Speak it!"), SEM exigir que seja
idêntica, palavra por palavra, à resposta esperada.

Critério de "certo":
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
import re
import time

import requests

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Número de tentativas extras se a chamada à Groq falhar por motivo de rede/
# timeout/erro 5xx (não por resposta inválida). Evita cair no fallback burro
# (comparação exata) por causa de um soluço passageiro de rede.
_MAX_RETRIES = 1

# Contrações comuns em inglês -> forma expandida. Usadas só para comparação
# determinística (pré-IA); não afetam o texto exibido ao aluno em nenhum
# momento. Cobrem os casos mais comuns o suficiente pra pegar respostas
# "obviamente certas" que só diferem por contração (ex.: "i am" vs "i'm").
_CONTRACTIONS = {
    r"\bi'm\b": "i am",
    r"\byou're\b": "you are",
    r"\bhe's\b": "he is",
    r"\bshe's\b": "she is",
    r"\bit's\b": "it is",
    r"\bwe're\b": "we are",
    r"\bthey're\b": "they are",
    r"\bthat's\b": "that is",
    r"\bwhat's\b": "what is",
    r"\bwho's\b": "who is",
    r"\bthere's\b": "there is",
    r"\bhere's\b": "here is",
    r"\bisn't\b": "is not",
    r"\baren't\b": "are not",
    r"\bwasn't\b": "was not",
    r"\bweren't\b": "were not",
    r"\bdon't\b": "do not",
    r"\bdoesn't\b": "does not",
    r"\bdidn't\b": "did not",
    r"\bcan't\b": "can not",
    r"\bcannot\b": "can not",
    r"\bwon't\b": "will not",
    r"\bwouldn't\b": "would not",
    r"\bcouldn't\b": "could not",
    r"\bshouldn't\b": "should not",
    r"\bhaven't\b": "have not",
    r"\bhasn't\b": "has not",
    r"\bhadn't\b": "had not",
    r"\bi've\b": "i have",
    r"\byou've\b": "you have",
    r"\bwe've\b": "we have",
    r"\bthey've\b": "they have",
    r"\bi'll\b": "i will",
    r"\byou'll\b": "you will",
    r"\bhe'll\b": "he will",
    r"\bshe'll\b": "she will",
    r"\bwe'll\b": "we will",
    r"\bthey'll\b": "they will",
    r"\bit'll\b": "it will",
    r"\bi'd\b": "i would",
    r"\byou'd\b": "you would",
    r"\bhe'd\b": "he would",
    r"\bshe'd\b": "she would",
    r"\bwe'd\b": "we would",
    r"\bthey'd\b": "they would",
    r"\blet's\b": "let us",
    # Gírias/contrações informais de fala (comuns em transcrição de áudio ou
    # digitação casual) -> forma padrão. Mesmo sentido, registro diferente;
    # tratamos como equivalentes.
    r"\bgonna\b": "going to",
    r"\bwanna\b": "want to",
    r"\bgotta\b": "got to",
    r"\btryna\b": "trying to",
    r"\bkinda\b": "kind of",
    r"\bsorta\b": "sort of",
    r"\blemme\b": "let me",
    r"\bgimme\b": "give me",
    r"\bdunno\b": "do not know",
    r"\by'all\b": "you all",
    r"\boutta\b": "out of",
    r"\bneeda\b": "need to",
    r"\bimma\b": "i am going to",
    r"\bfinna\b": "going to",
    r"\bcuz\b": "because",
}

# Formas sem apóstrofo das contrações acima (comuns em digitação rápida no
# celular ou em transcrição de fala). Geradas automaticamente a partir de
# _CONTRACTIONS, pulando os poucos casos ambíguos onde a forma sem apóstrofo
# já é uma palavra diferente com outro sentido (ex.: "its" é possessivo,
# "were" é passado de "to be", "well" é advérbio) — nesses casos, exigir o
# apóstrofo evita falso-positivo.
_AMBIGUOUS_WITHOUT_APOSTROPHE = {"its", "were", "well", "hell", "shed", "wed"}

for _pattern, _expansion in list(_CONTRACTIONS.items()):
    _word = _pattern[2:-2].replace("'", "")  # tira \b...\b e o apóstrofo
    if _word not in _AMBIGUOUS_WITHOUT_APOSTROPHE and rf"\b{_word}\b" not in _CONTRACTIONS:
        _CONTRACTIONS[rf"\b{_word}\b"] = _expansion

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

IMPORTANTE — coisas que NUNCA tornam uma resposta incorreta por si só:
- Maiúsculas/minúsculas (ex.: "where were you all morning?" == "Where were you all morning?").
- Pontuação a mais, a menos, ou diferente (ex.: "??" no lugar de "?", falta de ponto final).
- Contrações vs. forma expandida (ex.: "I'm" == "I am"; "didn't" == "did not").
- Gírias faladas informais vs. forma padrão, quando o sentido é o mesmo (ex.: "gonna"
  == "going to"; "wanna" == "want to"; "tryna" == "trying to"; "gotta" == "got to";
  "kinda" == "kind of"). Registro (formal vs. informal) não é erro de gramática.
- Espaços extras.
Se, ignorando essas diferenças, a resposta do aluno for a MESMA sequência de palavras que a
esperada (ou uma paráfrase de mesmo sentido), ela é CORRETA — não invente um problema de
sentido ou de gramática que não existe. Releia a frase com calma antes de decidir; um erro
de julgamento aqui prejudica o aluno.

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
            if "correct" not in parsed:
                raise ValueError("Resposta da IA sem o campo 'correct'.")
            return {
                "correct": bool(parsed["correct"]),
                "reason": str(parsed.get("reason", "")),
            }
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
            last_error = e
            # Erros de rede/timeout/5xx costumam ser passageiros — vale tentar
            # de novo antes de desistir e cair no fallback determinístico.
            if attempt < _MAX_RETRIES:
                logger.info("Tentativa %d de julgamento por IA falhou, tentando de novo: %s", attempt + 1, e)
                time.sleep(0.5)
                continue
    raise AiJudgeUnavailable(f"Falha ao consultar a API da Groq: {last_error}") from last_error


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

    # Atalho determinístico: se, ignorando maiúsculas, pontuação, espaços
    # extras e contrações (ex.: "I'm" vs "I am"), a resposta é a mesma
    # sequência de palavras da esperada, ela está certa — sem precisar
    # perguntar pra IA (mais rápido, mais barato, e evita casos em que o
    # modelo "inventa" um problema que não existe nesse tipo de diferença
    # puramente superficial).
    if _normalize(expected) == _normalize(given_clean):
        return {
            "correct": True,
            "reason": "Resposta corresponde à esperada (maiúsculas, pontuação ou contração à parte).",
            "ai_used": False,
        }

    try:
        result = _call_groq(expected, given_clean, context)
        correct = result["correct"]
        reason = result["reason"]
        # Rede de segurança: se a IA disse que está errado mas, na
        # comparação normalizada, a resposta bate com a esperada, isso é
        # sinal de alucinação do modelo (já vimos casos assim) — a
        # comparação determinística tem prioridade nesse cenário.
        if not correct and _normalize(expected) == _normalize(given_clean):
            correct = True
            reason = "Resposta corresponde à esperada (maiúsculas, pontuação ou contração à parte)."
        return {"correct": correct, "reason": reason, "ai_used": True}
    except AiJudgeUnavailable as e:
        logger.warning("Julgamento por IA indisponível, usando comparação exata: %s", e)
        fallback_correct = _normalize(expected) == _normalize(given_clean)
        reason = (
            "Resposta idêntica à esperada (IA indisponível no momento, comparação exata usada)."
            if fallback_correct
            else "Resposta diferente da esperada (IA indisponível no momento, comparação exata usada)."
        )
        return {"correct": fallback_correct, "reason": reason, "ai_used": False}


def _expand_contractions(text: str) -> str:
    result = text.lower()
    for pattern, expansion in _CONTRACTIONS.items():
        result = re.sub(pattern, expansion, result)
    return result


def _normalize(text: str) -> str:
    """Normaliza pra comparação determinística: minúsculas, contrações
    expandidas, sem pontuação, espaços colapsados. Só usada para decidir se
    duas respostas são "a mesma coisa escrita de formas superficialmente
    diferentes" — julgamento semântico de verdade continua com a IA."""
    text = _expand_contractions(text or "")
    text = re.sub(r"[^\w\s]", " ", text)  # remove toda pontuação
    text = re.sub(r"\s+", " ", text).strip()
    return text