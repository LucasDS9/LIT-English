"""
Seed multi-idioma do pacote de flashcards do primeiro acesso ao Aprender.

O catálogo é organizado por PAR de idiomas: língua de origem -> língua-alvo.
Hoje o script já envia:
    pt -> ingles
    pt -> italiano
    pt -> frances

Para adicionar futuramente, basta incluir outro par em STARTER_PACKS. Ex.:
    ("frances", "ingles"): [...]
    ("ingles", "alemao"): [...]

Uso no terminal:
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_starter_flashcards.py

Também é possível enviar somente um par:
    python scripts/seed_starter_flashcards.py --source pt --target italiano

Placeholders entre < > são preservados literalmente e detectados pelo backend.
"""
import argparse
import os
import sys
import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app").rstrip("/")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")


def card(front, back, description=None):
    return {"front": front, "back": back, "description": description}


# Descrições ficam em português porque, no momento, a língua de origem é PT.
# No futuro, ao criar FR->EN, EN->FR etc., a estrutura permite colocar a
# descrição na língua de origem daquele par sem alterar o restante do sistema.
DESCS = {
    1: "Forma informal e muito comum de cumprimentar alguém.",
    2: "Mais neutro que “Hi” e funciona em situações formais ou informais.",
    5: "Usado para cumprimentar alguém à noite.",
    6: "Usado ao se despedir ou quando alguém vai dormir.",
    7: "Forma informal de se despedir.",
    8: "Forma casual de se despedir.",
    11: "Forma casual de perguntar como a pessoa está.",
    12: "Pergunta casual sobre como estão as coisas.",
    16: "Usado para se apresentar.",
    17: "Usado ao conhecer alguém pela primeira vez.",
    21: "“Yet” indica que isso pode mudar com o tempo.",
    23: "Para perguntar o significado de algo.",
    25: "Quando você não ouviu ou não entendeu algo.",
    30: "Usado para pedir desculpas ou reconhecer um erro.",
    31: "Usado para chamar a atenção, interromper ou passar por alguém.",
    33: "Resposta comum a “Thank you”.",
    34: "Usado para tornar pedidos mais educados.",
    35: "Resposta comum a um pedido de desculpas ou agradecimento.",
    36: "Pode indicar que algo não é um problema.",
    37: "Usado para concordar ou aceitar algo.",
    38: "Uma forma enfática de concordar.",
    42: "Usado quando você não entendeu algo que foi dito.",
    43: "Útil quando você não consegue entender algo apenas ouvindo.",
    44: "Usado para pedir esclarecimento.",
    45: "Uma pergunta essencial em situações cotidianas.",
    46: "Usado para perguntar o preço de algo.",
    47: "Forma educada de dizer o que você quer.",
    49: "Despedida quando você espera ver a pessoa novamente em breve.",
    50: "Forma comum e educada de se despedir.",
}

# A fonte de verdade dos 50 cards. Cada pacote contém o mesmo conteúdo
# pedagógico, mas traduzido para a língua-alvo daquele par.
# Para criar um novo par no futuro, adicione uma nova chave aqui.
STARTER_PACKS = {
    ("pt", "ingles"): [
        card("Hi!", "Oi!", DESCS[1]),
        card("Hello!", "Olá!", DESCS[2]),
        card("Good morning!", "Bom dia!"),
        card("Good afternoon!", "Boa tarde!"),
        card("Good evening!", "Boa noite!", DESCS[5]),
        card("Good night!", "Boa noite!", DESCS[6]),
        card("Bye!", "Tchau!", DESCS[7]),
        card("See you later!", "Até mais!", DESCS[8]),
        card("See you tomorrow!", "Até amanhã!"),
        card("How are you?", "Como você está?"),
        card("How's it going?", "Como estão as coisas?", DESCS[11]),
        card("How's everything?", "Tudo bem?", DESCS[12]),
        card("I'm good, thank you.", "Estou bem, obrigado(a)."),
        card("I'm great!", "Estou ótimo(a)!"),
        card("What's your name?", "Qual é o seu nome?"),
        card("My name is <name>.", "Meu nome é <nome>.", DESCS[16]),
        card("Nice to meet you.", "Prazer em conhecer você.", DESCS[17]),
        card("I'm <age> years old.", "Tenho <idade> anos."),
        card("I'm <nationality>.", "Sou <nacionalidade>."),
        card("I'm learning <language>.", "Estou aprendendo <idioma>."),
        card("I don't understand <language> very well yet.", "Ainda não entendo <idioma> muito bem.", DESCS[21]),
        card("I don't understand this word.", "Não entendo essa palavra."),
        card("What does this mean?", "O que isso significa?", DESCS[23]),
        card("How do you say this in <language>?", "Como se diz isso em <idioma>?"),
        card("Can you repeat that, please?", "Pode repetir, por favor?", DESCS[25]),
        card("Can you speak more slowly, please?", "Pode falar mais devagar, por favor?"),
        card("Do you speak <language>?", "Você fala <idioma>?"),
        card("I don't know.", "Eu não sei."),
        card("Can you help me, please?", "Pode me ajudar, por favor?"),
        card("Sorry.", "Desculpa.", DESCS[30]),
        card("Excuse me.", "Com licença.", DESCS[31]),
        card("Thank you!", "Obrigado(a)!"),
        card("You're welcome!", "De nada!", DESCS[33]),
        card("Please.", "Por favor.", DESCS[34]),
        card("No problem.", "Não tem problema.", DESCS[35]),
        card("It's okay.", "Tudo bem.", DESCS[36]),
        card("Of course!", "Claro!", DESCS[37]),
        card("Absolutely!", "Com certeza!", DESCS[38]),
        card("Maybe.", "Talvez."),
        card("I think so.", "Acho que sim."),
        card("I don't think so.", "Acho que não."),
        card("I didn't understand.", "Não entendi.", DESCS[42]),
        card("Can you write it down, please?", "Pode escrever, por favor?", DESCS[43]),
        card("What do you mean?", "O que você quer dizer?", DESCS[44]),
        card("Where's the bathroom?", "Onde fica o banheiro?", DESCS[45]),
        card("How much is it?", "Quanto custa?", DESCS[46]),
        card("I'd like this.", "Eu gostaria disso.", DESCS[47]),
        card("I don't want this.", "Eu não quero isso."),
        card("See you soon!", "Até logo!", DESCS[49]),
        card("Have a good day!", "Tenha um bom dia!", DESCS[50]),
    ],
    ("pt", "italiano"): [
        card("Ciao!", "Oi!", DESCS[1]),
        card("Salve!", "Olá!", DESCS[2]),
        card("Buongiorno!", "Bom dia!"),
        card("Buon pomeriggio!", "Boa tarde!"),
        card("Buonasera!", "Boa noite!", DESCS[5]),
        card("Buonanotte!", "Boa noite!", DESCS[6]),
        card("Ciao!", "Tchau!", DESCS[7]),
        card("A dopo!", "Até mais!", DESCS[8]),
        card("A domani!", "Até amanhã!"),
        card("Come stai?", "Como você está?"),
        card("Come va?", "Como estão as coisas?", DESCS[11]),
        card("Come va tutto?", "Tudo bem?", DESCS[12]),
        card("Sto bene, grazie.", "Estou bem, obrigado(a)."),
        card("Sto benissimo!", "Estou ótimo(a)!"),
        card("Come ti chiami?", "Qual é o seu nome?"),
        card("Mi chiamo <nome>.", "Meu nome é <nome>.", DESCS[16]),
        card("Piacere di conoscerti.", "Prazer em conhecer você.", DESCS[17]),
        card("Ho <età> anni.", "Tenho <idade> anos."),
        card("Sono <nazionalità>.", "Sou <nacionalidade>."),
        card("Sto imparando <lingua>.", "Estou aprendendo <idioma>."),
        card("Non capisco ancora molto bene <lingua>.", "Ainda não entendo <idioma> muito bem.", DESCS[21]),
        card("Non capisco questa parola.", "Não entendo essa palavra."),
        card("Cosa significa?", "O que isso significa?", DESCS[23]),
        card("Come si dice questo in <lingua>?", "Como se diz isso em <idioma>?"),
        card("Puoi ripeterlo, per favore?", "Pode repetir, por favor?", DESCS[25]),
        card("Puoi parlare più lentamente, per favore?", "Pode falar mais devagar, por favor?"),
        card("Parli <lingua>?", "Você fala <idioma>?"),
        card("Non lo so.", "Eu não sei."),
        card("Puoi aiutarmi, per favore?", "Pode me ajudar, por favor?"),
        card("Scusa.", "Desculpa.", DESCS[30]),
        card("Scusi.", "Com licença.", DESCS[31]),
        card("Grazie!", "Obrigado(a)!"),
        card("Prego!", "De nada!", DESCS[33]),
        card("Per favore.", "Por favor.", DESCS[34]),
        card("Nessun problema.", "Não tem problema.", DESCS[35]),
        card("Va bene.", "Tudo bem.", DESCS[36]),
        card("Certo!", "Claro!", DESCS[37]),
        card("Assolutamente!", "Com certeza!", DESCS[38]),
        card("Forse.", "Talvez."),
        card("Penso di sì.", "Acho que sim."),
        card("Non credo.", "Acho que não."),
        card("Non ho capito.", "Não entendi.", DESCS[42]),
        card("Puoi scriverlo, per favore?", "Pode escrever, por favor?", DESCS[43]),
        card("Cosa intendi?", "O que você quer dizer?", DESCS[44]),
        card("Dov'è il bagno?", "Onde fica o banheiro?", DESCS[45]),
        card("Quanto costa?", "Quanto custa?", DESCS[46]),
        card("Vorrei questo.", "Eu gostaria disso.", DESCS[47]),
        card("Non voglio questo.", "Eu não quero isso."),
        card("A presto!", "Até logo!", DESCS[49]),
        card("Buona giornata!", "Tenha um bom dia!", DESCS[50]),
    ],
    ("pt", "frances"): [
        card("Salut !", "Oi!", DESCS[1]),
        card("Bonjour !", "Olá!", DESCS[2]),
        card("Bonjour !", "Bom dia!"),
        card("Bon après-midi !", "Boa tarde!"),
        card("Bonsoir !", "Boa noite!", DESCS[5]),
        card("Bonne nuit !", "Boa noite!", DESCS[6]),
        card("Salut !", "Tchau!", DESCS[7]),
        card("À plus tard !", "Até mais!", DESCS[8]),
        card("À demain !", "Até amanhã!"),
        card("Comment allez-vous ?", "Como você está?"),
        card("Ça va ?", "Como estão as coisas?", DESCS[11]),
        card("Comment ça va ?", "Tudo bem?", DESCS[12]),
        card("Je vais bien, merci.", "Estou bem, obrigado(a)."),
        card("Je vais très bien !", "Estou ótimo(a)!"),
        card("Comment vous appelez-vous ?", "Qual é o seu nome?"),
        card("Je m'appelle <nom>.", "Meu nome é <nome>.", DESCS[16]),
        card("Ravi(e) de vous rencontrer.", "Prazer em conhecer você.", DESCS[17]),
        card("J'ai <âge> ans.", "Tenho <idade> anos."),
        card("Je suis <nationalité>.", "Sou <nacionalidade>."),
        card("J'apprends <langue>.", "Estou aprendendo <idioma>."),
        card("Je ne comprends pas encore très bien <langue>.", "Ainda não entendo <idioma> muito bem.", DESCS[21]),
        card("Je ne comprends pas ce mot.", "Não entendo essa palavra."),
        card("Qu'est-ce que ça veut dire ?", "O que isso significa?", DESCS[23]),
        card("Comment dit-on ça en <langue> ?", "Como se diz isso em <idioma>?"),
        card("Pouvez-vous répéter, s'il vous plaît ?", "Pode repetir, por favor?", DESCS[25]),
        card("Pouvez-vous parler plus lentement, s'il vous plaît ?", "Pode falar mais devagar, por favor?"),
        card("Vous parlez <langue> ?", "Você fala <idioma>?"),
        card("Je ne sais pas.", "Eu não sei."),
        card("Pouvez-vous m'aider, s'il vous plaît ?", "Pode me ajudar, por favor?"),
        card("Désolé(e).", "Desculpa.", DESCS[30]),
        card("Excusez-moi.", "Com licença.", DESCS[31]),
        card("Merci !", "Obrigado(a)!"),
        card("De rien !", "De nada!", DESCS[33]),
        card("S'il vous plaît.", "Por favor.", DESCS[34]),
        card("Pas de problème.", "Não tem problema.", DESCS[35]),
        card("Ce n'est pas grave.", "Tudo bem.", DESCS[36]),
        card("Bien sûr !", "Claro!", DESCS[37]),
        card("Absolument !", "Com certeza!", DESCS[38]),
        card("Peut-être.", "Talvez."),
        card("Je pense que oui.", "Acho que sim."),
        card("Je ne pense pas.", "Acho que não."),
        card("Je n'ai pas compris.", "Não entendi.", DESCS[42]),
        card("Pouvez-vous l'écrire, s'il vous plaît ?", "Pode escrever, por favor?", DESCS[43]),
        card("Qu'est-ce que vous voulez dire ?", "O que você quer dizer?", DESCS[44]),
        card("Où sont les toilettes ?", "Onde fica o banheiro?", DESCS[45]),
        card("Combien ça coûte ?", "Quanto custa?", DESCS[46]),
        card("Je voudrais ça.", "Eu gostaria disso.", DESCS[47]),
        card("Je ne veux pas ça.", "Eu não quero isso."),
        card("À bientôt !", "Até logo!", DESCS[49]),
        card("Passez une bonne journée !", "Tenha um bom dia!", DESCS[50]),
    ],
}


def normalize_lang(value):
    raw = str(value or "").strip().lower()
    aliases = {
        "pt-br": "pt", "portugues": "pt", "português": "pt",
        "en": "ingles", "inglês": "ingles", "english": "ingles",
        "it": "italiano", "italiano": "italiano",
        "fr": "frances", "francês": "frances", "français": "frances",
    }
    return aliases.get(raw, raw)


def main():
    if not PROFESSOR_EMAIL or not PROFESSOR_PASSWORD:
        print("Defina PROFESSOR_EMAIL e PROFESSOR_PASSWORD nas variáveis de ambiente.")
        print('Ex.: PROFESSOR_EMAIL="seu-email@exemplo.com" PROFESSOR_PASSWORD="sua-senha" python scripts/seed_starter_flashcards.py')
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Seed dos flashcards iniciais por par de idiomas.")
    parser.add_argument("--source", help="Língua de origem, ex.: pt")
    parser.add_argument("--target", help="Língua-alvo, ex.: italiano")
    args = parser.parse_args()

    selected = []
    if args.source or args.target:
        if not (args.source and args.target):
            parser.error("Use --source e --target juntos.")
        pair = (normalize_lang(args.source), normalize_lang(args.target))
        if pair not in STARTER_PACKS:
            available = ", ".join(f"{a}->{b}" for a, b in STARTER_PACKS)
            parser.error(f"Par não cadastrado: {pair[0]}->{pair[1]}. Disponíveis: {available}")
        selected = [pair]
    else:
        selected = list(STARTER_PACKS.keys())

    for pair in selected:
        if len(STARTER_PACKS[pair]) != 50:
            raise RuntimeError(f"{pair[0]}->{pair[1]} deveria ter 50 cards, mas tem {len(STARTER_PACKS[pair])}.")

    print(f"Fazendo login em {API_BASE_URL}...")
    login_resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        data={"username": PROFESSOR_EMAIL, "password": PROFESSOR_PASSWORD},
        timeout=30,
    )
    login_resp.raise_for_status()
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for source_language, target_language in selected:
        payload = {
            "source_language": source_language,
            "language": target_language,
            "cards": [
                {**item, "category": "saudacoes"}
                for item in STARTER_PACKS[(source_language, target_language)]
            ],
        }
        resp = requests.post(
            f"{API_BASE_URL}/flashcards/starter/catalog",
            json=payload,
            headers=headers,
            timeout=60,
        )
        if resp.status_code >= 400:
            print(f"Falha em {source_language}->{target_language}: {resp.status_code} {resp.text}")
            sys.exit(1)

        result = resp.json()
        print(
            f"[OK] {source_language}->{target_language} | "
            f"criados={result.get('created', 0)} | "
            f"atualizados={result.get('updated', 0)} | "
            f"inalterados={result.get('unchanged', 0)} | "
            f"total={result.get('total', 0)}"
        )

    print("Seed multi-idioma concluído.")
    print("Placeholders entre < > são detectados automaticamente pelo backend e preservados no card.")


if __name__ == "__main__":
    main()
