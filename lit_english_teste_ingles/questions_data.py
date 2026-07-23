# -*- coding: utf-8 -*-
"""
Banco de questões do teste LIT English.

Tipos de questão:
- "fill"        -> múltipla escolha, preencher lacuna
- "translation" -> resposta livre (EN -> PT), corrigida por similaridade de texto
- "listening"   -> múltipla escolha, o áudio é a própria frase em inglês
                    (o front-end vai usar SpeechSynthesis para "falar" question_en)

Cada questão tem:
- id: identificador único (int) -> usado como chave nas respostas do aluno
- number: posição de exibição (1..12)
- type: fill | translation | listening
- level: A1 | A2 | B1  (usado no sistema de pontos e nivelamento)
- subject: assunto gramatical (mostrado como "ASSUNTO" na tela)
- question_en: frase em inglês (com "____" quando for lacuna)
- translation_pt: tradução mostrada como apoio (quando aplicável)
- options: lista de alternativas (para fill/listening)
- correct_key: chave da alternativa correta (para fill/listening)
- accepted_answers: lista de respostas aceitas, já normalizadas (para translation)
- reference_answer: resposta "oficial" mostrada no feedback (para translation)
- direction: "en_pt" (mostra question_en, traduz p/ português) ou
  "pt_en" (mostra question_pt, traduz p/ inglês) — só para translation
- question_pt: frase em português mostrada quando direction == "pt_en"

IMPORTANTE sobre o campo "feedback" (fill):
Cada opção tem um texto NEUTRO explicando a gramática daquela alternativa
(por que ela está certa ou por que está errada). Esse texto NÃO deve conter
a palavra "Correto!" — quem decide se mostra "Correto!" (quando o aluno
acerta) ou "O correto seria... / Você escolheu..." (quando erra) é a
camada de correção (grading.py), e não o dado em si. Isso evita o bug de
aparecer "Correto!" na tela mesmo quando a resposta do aluno estava errada.

Sobre "grammar_note" (translation):
Explicação neutra da regra gramatical usada na frase. A camada de correção
usa esse texto tanto para "Correto! ..." (quando acerta) quanto para compor
a explicação de erro (quando erra).

Sobre "feedback" (listening):
Para as questões de listening, o texto de cada opção já é uma explicação
completa e específica (no estilo "o que você confundiu no áudio"), então
a camada de correção apenas exibe o texto da opção escolhida como está,
acrescentando "Correto!" na frente quando for a opção certa.
"""

QUESTIONS = [
    {
        "id": 1,
        "number": 1,
        "type": "fill",
        "level": "A1",
        "subject": "Verb To Be",
        "question_en": "I ____ confident.",
        "translation_pt": "Eu sou confiante.",
        "options": [
            {"key": "a", "text": "are",
             "feedback": "\u201cAre\u201d \u00e9 usado com you, we e they. Como o sujeito \u00e9 I, o certo \u00e9 am.",
             "tip": "Memorize o verbo to be: I am | You are | He/She is..."},
            {"key": "b", "text": "is",
             "feedback": "\u201cIs\u201d acompanha he, she e it. Como o sujeito \u00e9 I, o certo \u00e9 am.",
             "tip": "Primeiro identifique o sujeito e memorize o verbo to be."},
            {"key": "c", "text": "am",
             "feedback": "\u201cI am\u201d \u00e9 a forma correta do verbo to be quando o sujeito \u00e9 I.",
             "tip": "O verbo to be muda conforme a pessoa. Nunca escolha am, is ou are antes de identificar quem \u00e9 o sujeito."},
            {"key": "d", "text": "was",
             "feedback": "\u201cWas\u201d est\u00e1 no passado (era/estava), mas a frase est\u00e1 no presente. Com I, o certo \u00e9 am.",
             "tip": "O verbo was significa era ou estava. Sempre confira se esse \u00e9 realmente o significado que a frase precisa."},
        ],
        "correct_key": "c",
    },
    {
        "id": 2,
        "number": 2,
        "type": "fill",
        "level": "A2",
        "subject": "Past Simple",
        "question_en": "She ____ to the hospital yesterday.",
        "translation_pt": "Ela foi para o hospital ontem.",
        "options": [
            {"key": "a", "text": "go",
             "feedback": "\u201cYesterday\u201d indica que a a\u00e7\u00e3o aconteceu no passado, por isso precisamos do Past Simple: went.",
             "tip": "Yesterday → Past Simple."},
            {"key": "b", "text": "gone",
             "feedback": "\u201cGone\u201d \u00e9 o partic\u00edpio passado e precisa de have/has/had. Sozinho, o certo \u00e9 went.",
             "tip": "Memorize: go → went → gone."},
            {"key": "c", "text": "went",
             "feedback": "\u201cWent\u201d \u00e9 o passado de go, usado para a\u00e7\u00f5es que j\u00e1 aconteceram (indicadas por yesterday).",
             "tip": "Sempre que encontrar yesterday, pense em Past Simple."},
            {"key": "d", "text": "was",
             "feedback": "\u201cWas\u201d \u00e9 o verbo to be, mas o verbo principal da frase \u00e9 go (foi), por isso o certo \u00e9 went.",
             "tip": "Identifique qual \u00e9 o verbo principal da frase."},
            {"key": "e", "text": "going",
             "feedback": "\u201cGoing\u201d precisa de um verbo auxiliar (am/is/are/was/were). No Past Simple, o certo \u00e9 went.",
             "tip": "Verbos terminados em -ing normalmente precisam de um verbo auxiliar."},
        ],
        "correct_key": "c",
    },
    {
        "id": 3,
        "number": 3,
        "type": "fill",
        "level": "A1",
        "subject": "Present Simple",
        "question_en": "My brother ____ coffee every morning.",
        "translation_pt": "Meu irmão bebe café toda manhã.",
        "options": [
            {"key": "a", "text": "drink",
             "feedback": "Com he/she acrescentamos -s ao verbo no Present Simple. O certo \u00e9 drinks.",
             "tip": "He/She + verbo + s."},
            {"key": "b", "text": "drinks",
             "feedback": "A frase fala de uma rotina (every morning), por isso usamos drinks com he/she no Present Simple.",
             "tip": "Express\u00f5es como every morning normalmente indicam Present Simple."},
            {"key": "c", "text": "drank",
             "feedback": "\u201cDrank\u201d est\u00e1 no passado, mas a frase descreve um h\u00e1bito atual. O certo \u00e9 drinks.",
             "tip": "Rotinas usam Present Simple."},
            {"key": "d", "text": "drinking",
             "feedback": "\u201cDrinking\u201d precisa de um verbo auxiliar. Para uma rotina no Present Simple, o certo \u00e9 drinks.",
             "tip": "Verbos em -ing n\u00e3o aparecem sozinhos."},
        ],
        "correct_key": "b",
    },
    {
        "id": 4,
        "number": 4,
        "type": "fill",
        "level": "A2",
        "subject": "First Conditional",
        "question_en": "If it ____ tomorrow, we ____ stay at home.",
        "translation_pt": "Se chover amanhã, ficaremos em casa.",
        "options": [
            {"key": "a", "text": "rain, will",
             "feedback": "Depois de if, no First Conditional, usamos o verbo com -s: rains.",
             "tip": "First Conditional = If + Present Simple + will."},
            {"key": "b", "text": "rained, are going to",
             "feedback": "Essa combina\u00e7\u00e3o mistura tempos verbais. O First Conditional usa rains, will.",
             "tip": "Use sempre a estrutura completa da First Conditional."},
            {"key": "c", "text": "rains, will",
             "feedback": "Essa \u00e9 a estrutura da First Conditional: If + Present Simple, will + verbo.",
             "tip": "If + Present → Will + verbo."},
            {"key": "d", "text": "rain, going to",
             "feedback": "\u201cGoing to\u201d precisa do verbo be (are going to). O certo aqui \u00e9 rains, will.",
             "tip": "Lembre-se da estrutura be going to."},
        ],
        "correct_key": "c",
    },
    {
        "id": 5,
        "number": 5,
        "type": "fill",
        "level": "A2",
        "subject": "Past Continuous",
        "question_en": "The teachers ____ giving their classes.",
        "translation_pt": "Os professores estavam dando suas aulas.",
        "options": [
            {"key": "a", "text": "were",
             "feedback": "\u201cTeachers\u201d est\u00e1 no plural, e a frase est\u00e1 no passado, por isso usamos were (Past Continuous).",
             "tip": "Plural → were."},
            {"key": "b", "text": "are",
             "feedback": "\u201cAre\u201d deixa a frase no presente, mas a frase est\u00e1 no passado. O certo \u00e9 were.",
             "tip": "Was/Were + ing = passado cont\u00ednuo."},
            {"key": "c", "text": "was",
             "feedback": "\u201cWas\u201d \u00e9 usado com sujeitos no singular. Como teachers est\u00e1 no plural, o certo \u00e9 were.",
             "tip": "Teacher was | Teachers were."},
            {"key": "d", "text": "is",
             "feedback": "\u201cIs\u201d \u00e9 singular e est\u00e1 no presente. Para teachers no passado, o certo \u00e9 were.",
             "tip": "Observe o sujeito e o tempo verbal."},
        ],
        "correct_key": "a",
    },

    # ---------------- TRANSLATION (resposta livre) ----------------
    # Campo "direction":
    #   "en_pt" -> mostra a frase em inglês (question_en), aluno traduz para o português
    #   "pt_en" -> mostra a frase em português (question_pt), aluno traduz para o inglês
    {
        "id": 6,
        "number": 6,
        "type": "translation",
        "direction": "en_pt",
        "level": "A2",
        "subject": "Past Continuous",
        "question_en": "I was studying.",
        "reference_answer": "Eu estava estudando.",
        "accepted_answers": [
            "eu estava estudando",
            "eu tava estudando",
        ],
        "grammar_note": "A frase usa was + verbo-ing (studying), que \u00e9 a estrutura do Past Continuous e indica algo que estava acontecendo no passado.",
        "tip": "Quando encontrar was/were + verbo-ing, pense em Past Continuous.",
    },
    {
        "id": 7,
        "number": 7,
        "type": "translation",
        "direction": "en_pt",
        "level": "B1",
        "subject": "Conditional",
        "question_en": "I wouldn't like that.",
        "reference_answer": "Eu não gostaria disso.",
        "accepted_answers": [
            "eu nao gostaria disso",
            "eu nao iria gostar disso",
            "eu nao gostaria disto",
            "eu nao iria gostar disto",
        ],
        "grammar_note": "Wouldn't (would not) indica uma situa\u00e7\u00e3o hipot\u00e9tica, por isso a tradu\u00e7\u00e3o usa o condicional \u201cgostaria\u201d.",
        "tip": "Would é muito usado para falar de situações hipotéticas ou fazer pedidos educados.",
    },
    {
        "id": 8,
        "number": 8,
        "type": "translation",
        "direction": "en_pt",
        "level": "A2",
        "subject": "Comparatives",
        "question_en": "My car is faster than yours.",
        "reference_answer": "Meu carro é mais rápido que o seu.",
        "accepted_answers": [
            "meu carro e mais rapido que o seu",
            "meu carro e mais rapido que o teu",
            "meu carro e mas rapido que o teu",
        ],
        "grammar_note": "Faster \u00e9 o comparativo de fast (r\u00e1pido), formado com -er, e than corresponde a \u201cque\u201d na compara\u00e7\u00e3o.",
        "tip": "Adjetivos curtos normalmente recebem -er no comparativo.",
    },
    {
        "id": 9,
        "number": 9,
        "type": "translation",
        "direction": "en_pt",
        "level": "A2",
        "subject": "Modal Verbs",
        "question_en": "You should call him.",
        "reference_answer": "Você deveria ligar para ele.",
        "accepted_answers": [
            "voce deveria ligar para ele",
            "voce deveria ligar pra ele",
            "voce deveria liga-lo",
            "voce deveria liga lo",
        ],
        "grammar_note": "Should expressa um conselho, por isso a tradu\u00e7\u00e3o usa \u201cdeveria\u201d.",
        "tip": "Should é usado para dar conselhos.",
    },
    {
        "id": 10,
        "number": 10,
        "type": "translation",
        "direction": "en_pt",
        "level": "B1",
        "subject": "Concession Clauses",
        "question_en": "Although he was tired, he decided to finish the project.",
        "reference_answer": "Embora ele estivesse cansado, decidiu terminar o projeto.",
        "accepted_answers": [
            "embora ele estivesse cansado decidiu terminar o projeto",
            "embora estivesse cansado ele decidiu terminar o projeto",
            "embora ele estivesse cansado ele decidiu terminar o projeto",
        ],
        "grammar_note": "Although liga duas ideias opostas (estar cansado x decidir terminar o projeto), por isso usamos \u201cembora\u201d na tradu\u00e7\u00e3o.",
        "tip": "Although significa embora e liga duas ideias opostas.",
    },

    # ---------------- TRANSLATION PT -> EN (frases simples e simpáticas, A1) ----------------
    {
        "id": 13,
        "number": 13,
        "type": "translation",
        "direction": "pt_en",
        "level": "A1",
        "subject": "Greetings & Politeness",
        "question_pt": "Obrigado(a) pela sua ajuda!",
        "reference_answer": "Thank you for your help!",
        "accepted_answers": [
            "thank you for your help",
            "thanks for your help",
            "thank you very much for your help",
            "thank you so much for your help",
            "thanks a lot for your help",
            "thanks very much for your help",
        ],
        "grammar_note": "Thank you \u00e9 a forma mais comum de agradecer em ingl\u00eas, e for + substantivo (for your help) indica o motivo do agradecimento.",
        "tip": "Thank you for + motivo é a estrutura mais usada para agradecer em inglês.",
    },
    {
        "id": 14,
        "number": 14,
        "type": "translation",
        "direction": "pt_en",
        "level": "A1",
        "subject": "Common Expressions",
        "question_pt": "Tenha um ótimo dia!",
        "reference_answer": "Have a great day!",
        "accepted_answers": [
            "have a great day",
            "have a nice day",
            "have a good day",
        ],
        "grammar_note": "Have a + adjetivo + day \u00e9 uma express\u00e3o fixa de despedida, formada com o verbo have no imperativo (sem sujeito, como um pedido/desejo).",
        "tip": "Frases de despedida com have a... não precisam de sujeito (imperativo).",
    },

    # ---------------- LISTENING (múltipla escolha) ----------------
    {
        "id": 11,
        "number": 11,
        "type": "listening",
        "level": "A1",
        "subject": "Listening",
        "question_en": "My sister usually walks to school because she lives nearby.",
        "options": [
            {"key": "a", "text": "Minha irmã normalmente vai para a escola de ônibus porque mora longe.",
             "feedback": "Quase! Voc\u00ea confundiu duas palavras importantes do \u00e1udio.\n\u2022 walks = vai caminhando\n\u2022 by bus = de \u00f4nibus\nE tamb\u00e9m:\n\u2022 nearby = perto\n\u2022 far = longe\nEssas duas trocas mudam completamente o significado da frase. Na pr\u00f3xima, tente prestar aten\u00e7\u00e3o principalmente nas palavras que indicam como a pessoa se desloca e onde ela mora."},
            {"key": "b", "text": "Minha irmã geralmente vai caminhando para a escola porque mora perto.",
             "feedback": "Voc\u00ea identificou corretamente as palavras-chave do \u00e1udio:\n\u2022 walks = vai caminhando\n\u2022 nearby = perto\nContinue assim! Ouvir essas pequenas palavras faz toda a diferen\u00e7a no listening."},
            {"key": "c", "text": "Minha irmã gosta de caminhar no parque perto da escola.",
             "feedback": "Boa tentativa! Voc\u00ea percebeu a palavra walks, mas confundiu o restante da frase.\nNo \u00e1udio: walks to school = vai caminhando para a escola\nNesta alternativa: likes walking in the park = gosta de caminhar no parque\nAs duas frases falam sobre caminhar, mas em contextos completamente diferentes."},
            {"key": "d", "text": "Minha irmã sempre vai de bicicleta para a escola.",
             "feedback": "Voc\u00ea confundiu o meio de transporte.\nNo \u00e1udio: walks = vai caminhando\nNesta alternativa: by bike / rides a bike = vai de bicicleta\nFique de olho nas palavras que mostram o meio de transporte ou a forma de locomo\u00e7\u00e3o."},
        ],
        "correct_key": "b",
        "tip": "Escute primeiro as palavras-chave, como walks e nearby.",
    },
    {
        "id": 12,
        "number": 12,
        "type": "listening",
        "level": "A2",
        "subject": "Listening",
        "question_en": "We have a meeting at nine o'clock, so don't be late.",
        "options": [
            {"key": "a", "text": "Temos uma reunião às oito horas, então não se atrase.",
             "feedback": "Voc\u00ea entendeu quase toda a frase! O detalhe que mudou foi o hor\u00e1rio.\nNo \u00e1udio: nine = nove\nVoc\u00ea escolheu: eight = oito\nN\u00fameros costumam ser um dos pontos que mais confundem no listening. Vale a pena ouvir essa parte mais uma vez."},
            {"key": "b", "text": "Tivemos uma reunião às nove horas, então não se atrase.",
             "feedback": "Quase! Voc\u00ea acertou o hor\u00e1rio, mas confundiu o verbo.\nNo \u00e1udio: have = temos\nVoc\u00ea escolheu: had = tivemos\nEssas palavrinhas s\u00e3o muito parecidas na pron\u00fancia, mas mudam completamente o tempo da frase."},
            {"key": "c", "text": "Temos uma reunião às nove horas, então tente chegar cedo.",
             "feedback": "Voc\u00ea acertou o come\u00e7o da frase, mas o final mudou.\nNo \u00e1udio: Don't be late. = N\u00e3o se atrase.\nNesta alternativa: Try to arrive early. = Tente chegar cedo.\nAs duas frases s\u00e3o parecidas, mas transmitem mensagens diferentes. Tente prestar aten\u00e7\u00e3o at\u00e9 o final do \u00e1udio antes de responder."},
            {"key": "d", "text": "Temos uma reunião às nove horas, então não se atrase.",
             "feedback": "Voc\u00ea identificou corretamente todas as informa\u00e7\u00f5es importantes:\n\u2022 have = temos\n\u2022 nine = nove\n\u2022 don't be late = n\u00e3o se atrase\nExcelente! Continue focando nas palavras-chave. Elas normalmente carregam a informa\u00e7\u00e3o mais importante da frase."},
        ],
        "correct_key": "d",
        "tip": "Preste atenção em números e expressões de tempo.",
    },

    # ---------------- TRANSLATION EN -> PT (B1) ----------------
    {
        "id": 15,
        "number": 15,
        "type": "translation",
        "direction": "en_pt",
        "level": "B1",
        "subject": "Passive Voice",
        "question_en": "The window was broken by the wind.",
        "reference_answer": "A janela foi quebrada pelo vento.",
        "accepted_answers": [
            "a janela foi quebrada pelo vento",
            "a janela foi quebrada pelo vento forte",
        ],
        "grammar_note": "Na voz passiva, o sujeito (a janela) recebe a a\u00e7\u00e3o em vez de pratic\u00e1-la: was + particípio (broken), e by introduz quem praticou a a\u00e7\u00e3o (pelo vento).",
        "tip": "Voz passiva = was/were + particípio. Quem pratica a ação vem depois de by.",
    },
]

# Índice rápido por id
QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}

TOTAL_QUESTIONS = len(QUESTIONS)  # 15
