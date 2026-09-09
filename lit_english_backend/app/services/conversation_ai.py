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

import asyncio
import json
import logging
import os

import httpx

logger = logging.getLogger("lit.conversation_ai")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

# Erros de rede/timeout/5xx costumam ser passageiros -- vale tentar de novo
# antes de desistir (mesmo critério usado em ai_judge.py).
_MAX_RETRIES = 2

# Temperature mais alta e mais espaço de tokens deixam o "tutor_reply" menos
# mecânico/repetitivo. A análise gramatical (campo "errors") continua sendo
# extraída do MESMO JSON, mas por ser um julgamento objetivo (achar erro x
# não achar) tolera bem essa temperature -- quem ganha variedade é a parte
# de conversa.
_TEMPERATURE = 0.7
_MAX_TOKENS = 900

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
reconhecimento de voz (ASR).

IMPORTANTE -- A TRANSCRIÇÃO PODE ESTAR ERRADA, NÃO SÓ O ALUNO:
Reconhecimento de voz erra por SOM, não por sentido. Antes de analisar qualquer coisa, releia a
transcrição pensando: "isso faz sentido no contexto da conversa? existe uma palavra parecida
FONETICAMENTE que faria mais sentido aqui?". Exemplos do tipo de erro a corrigir mentalmente:
  - Palavra sem sentido no contexto, mas foneticamente parecida com uma que faz sentido
    (ex.: ASR ouviu "petra" onde o aluno claramente disse "pedra", porque soam parecido).
  - Nomes próprios, gírias ou palavras raras podem sair grafadas de forma estranha/fonética.
  - Pontuação e capitalização da transcrição são pouco confiáveis -- o ASR frequentemente erra
    onde põe vírgula, maiúscula ou ponto de interrogação.
  - Se o aluno claramente está PERGUNTANDO algo (estrutura de pergunta, palavra interrogativa tipo
    "o que", "why", "how", tom de dúvida) trate como pergunta MESMO que a transcrição não tenha
    "?" no final -- o ASR frequentemente omite o "?".
  - Se uma palavra aparece sozinha, isolada, repetida, ou com hesitação antes/depois (ex.: "hmm...
    pedra... pedra"), o aluno provavelmente está tentando pronunciar/citar aquela palavra
    especificamente (praticando vocabulário/pronúncia), não formando uma frase gramatical --
    não marque isso como "frase incompleta" nem como erro de gramática.
  - Quando o aluno está claramente CITANDO uma palavra ou frase (pedindo tradução, perguntando o
    significado, repetindo pra praticar), trate essa palavra citada como vocabulário -- não como
    parte da frase gramatical dele a ser corrigida.
Use o campo "understood_transcript" (ver formato abaixo) para registrar sua MELHOR interpretação
da fala real do aluno depois dessas correções -- é isso que deve ser usado como base pra tudo
daqui pra frente (análise gramatical E resposta), não a transcrição bruta se ela não fizer sentido.
Só analise como erro de GRAMÁTICA o que sobrar depois de descontar prováveis erros de reconhecimento
de voz -- nunca invente um erro gramatical a partir de uma transcrição ruim.

IMPORTANTE SOBRE AS DUAS LÍNGUAS:
- A língua-alvo é a língua que o aluno está aprendendo: {target_language}.
- A língua nativa é {native_language}.
- O aluno pode misturar as duas línguas de propósito, especialmente para pedir ajuda de vocabulário,
  e pode até trocar de língua NO MEIO da mesma frase (code-switching) -- isso é normal, não é erro.
- Entenda pedidos equivalentes a “how can I say X in {target_language}?”, “how do I say X in {target_language}?”,
  “como posso dizer X em {target_language}?”, “como se diz X em {target_language}?”, e equivalentes na própria língua nativa ou alvo.
- Quando o aluno pedir como dizer uma palavra/expressão da língua nativa na língua-alvo, dê diretamente a tradução natural
  e, se útil, um exemplo curto. A resposta falada continua na língua-alvo; não trate a palavra da língua nativa como erro gramatical.
- Se a fala estiver na língua nativa porque o aluno está pedindo ajuda, isso NÃO é um erro.

Sua tarefa tem três partes:

1) ENTENDIMENTO DA FALA (campo "understood_transcript"):
   - Sua melhor reconstrução do que o aluno REALMENTE disse, corrigindo prováveis erros de ASR
     (fonética, pontuação, palavras isoladas/citadas) como descrito acima.
   - Se a transcrição bruta já fizer sentido perfeito, "understood_transcript" pode ser igual a ela.
   - Isso é a base pra tudo que vem depois -- análise gramatical e resposta.

2) ANÁLISE GRAMATICAL da fala do aluno, com base no "understood_transcript" (campo "errors"):
   - Procure ativamente erros reais de gramática na língua-alvo.
   - Cada erro deve conter wrong_fragment, correct_fragment e uma explicação curta em {native_language}.
   - Não invente erros, mas também não ignore erros reais.
   - NUNCA transforme uma correção de ASR (fonética) em "erro de gramática" do aluno.
   - "corrected_sentence": a frase inteira corrigida na língua-alvo. Para um pedido de vocabulário/tradução, deixe errors vazio e use uma string vazia em corrected_sentence.
   - "feedback_native": uma frase curta e encorajadora na língua nativa do aluno.

3) CONTINUAÇÃO DA CONVERSA (campo "tutor_reply"):
   - Responda EXCLUSIVAMENTE na língua-alvo {target_language}.
   - Seja natural, caloroso e variado no tom -- evite soar como um roteiro fixo ou repetir a
     mesma estrutura de frase toda vez ("That's interesting! Tell me more about..." em todo turno
     é o tipo de coisa a EVITAR).
   - NÃO faça uma pergunta genérica de continuidade. Pegue um detalhe CONCRETO que o aluno
     mencionou (um nome, lugar, opinião, sentimento) e reaja a esse detalhe especificamente --
     comente, questione ou brinque com ele antes de, se fizer sentido, perguntar algo novo.
   - Varie a forma da resposta: às vezes uma reação curta + pergunta, às vezes um comentário sem
     pergunta nenhuma, às vezes compartilhar uma opinião própria breve. Uma conversa real não é
     uma pergunta atrás da outra.
   - Se o aluno claramente pediu o significado/tradução de uma palavra (ver "citação" acima),
     responda dando a tradução/explicação daquela palavra especificamente, não mude de assunto.
   - Não repita a correção gramatical em voz alta.
   - Ajuste a complexidade do vocabulário e das estruturas ao nível do aluno, mas sem infantilizar.

Exemplos do tipo de "tutor_reply" esperado (aluno praticando inglês; NÃO copie o texto, é só pra
ilustrar tom e variedade -- reaja sempre ao que o SEU aluno disse):
- Aluno disse que foi mal numa prova: "Ugh, that's the worst feeling. Was it the material itself,
  or just not enough time to study?"
- Aluno disse que gosta de futebol e torce pro Flamengo: "No way, a Flamengo fan! I've heard their
  fans are some of the loudest in the world. Have you been to a game at the stadium?"
- Aluno só disse "eu não sei": "Totally fine -- no pressure. Want to talk about your day instead?"

Se a fala estiver vazia ou incompreensível mesmo depois de tentar corrigir o ASR, deixe errors
vazio, escreva feedback_native na língua nativa e peça gentilmente para o aluno repetir em
{target_language}.

Responda APENAS com JSON válido, no formato exato:
{{
  "understood_transcript": "...",
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


async def _call_groq(messages: list[dict]) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ConversationAiUnavailable("GROQ_API_KEY não configurada.")

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": _TEMPERATURE,
        "max_tokens": _MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=25.0) as client:
        for attempt in range(_MAX_RETRIES + 1):
            try:
                r = await client.post(
                    GROQ_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                r.raise_for_status()
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                usage = data.get("usage") or {}
                input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
                output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)

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
                    "understood_transcript": str(parsed.get("understood_transcript", "")).strip(),
                    "errors": errors,
                    "corrected_sentence": str(parsed.get("corrected_sentence", "")).strip(),
                    "feedback_native": feedback_native,
                    # Compatibility with older frontend/backend consumers.
                    "feedback_pt_br": feedback_native,
                    "tutor_reply": tutor_reply,
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                        "model": GROQ_MODEL,
                    },
                }
            except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError) as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    logger.info("Tentativa %d da Conversa IA falhou, tentando de novo: %s", attempt + 1, e)
                    await asyncio.sleep(0.6)
                    continue

    raise ConversationAiUnavailable(f"Falha ao consultar a API da Groq: {last_error}") from last_error


async def get_tutor_turn(
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
    return await _call_groq(messages)
