"""
Script de seed: cria/atualiza os decks abaixo (extraídos do documento de
vocabulário do professor) e já envia cada deck, como um bloco no Histórico,
para os alunos-alvo definidos em TARGET_STUDENT_NAMES.

Cada frase do front vem com o nome do tema na frente (ex.: "Past: They were
busy"), pra o aluno ver de qual assunto é a frase direto na tela de Revisar.

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_flashcards_from_doc.py

O script:
  1. Faz login como professor.
  2. Busca a lista de alunos aprovados no momento e filtra pelos nomes em
     TARGET_STUDENT_NAMES (None = todos os aprovados).
  3. Apaga flashcards antigos que serão substituídos:
       - TARGET_STUDENT_NAMES = None: apaga TODOS os flashcards cadastrados.
       - TARGET_STUDENT_NAMES = [nomes específicos]: apaga só os decks cujo
         nome bate com um tema de DECKS e que já tinham sido enviados
         exclusivamente para os alunos-alvo — assim rodar de novo (ex.: após
         atualizar o texto de um card) atualiza o que esses alunos já têm,
         em vez de duplicar. Vocabulário de outros alunos não é tocado.
  4. Cria um deck (bloco no Histórico) por tópico gramatical, com os
     flashcards abaixo, já atribuído aos alunos-alvo.

Para restringir/alterar quem recebe os decks, edite `TARGET_STUDENT_NAMES`
logo abaixo (None = todos os alunos aprovados).
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# Se quiser restringir o envio a alunos específicos, liste os nomes exatos
# (como aparecem em /admin/students) aqui. None = todos os alunos aprovados.
TARGET_STUDENT_NAMES = ["Daniel", "Andrielle"]


# ---------------------------------------------------------------------------
# Decks extraídos do documento (front = inglês, back = português)
# ---------------------------------------------------------------------------
DECKS = {
    "Past": [
        ("Past: They were busy", "eles estavam ocupados"),
        ("Past: It was cold", "estava frio"),
        ("Past: I needed help", "eu precisava de ajuda"),
        ("Past: We bought a lot of things", "nós compramos várias coisas"),
        ("Past: I went to school yesterday", "eu fui para a escola ontem"),
        ("Past: My brother was not there", "meu irmão não estava lá"),
        ("Past: It wasn't difficult", "não foi difícil"),
        ("Past: I did not watch TV", "eu não assisti TV"),
    ],
    "Future": [
        ("Future: They will be there.", "eles estarão lá."),
        ("Future: We will try.", "nós tentaremos."),
        ("Future: I'm about to leave.", "estou prestes a sair."),
        ("Future: I will not give up.", "eu não vou desistir."),
        ("Future: We won't be available.", "nós não estaremos disponíveis."),
        ("Future: You won't believe what just happened.", "você não vai acreditar no que acabou de acontecer."),
        ("Future: We are gonna stay.", "nós vamos ficar."),
        ("Future: We are going to John's house.", "nós vamos para a casa do John."),
        ("Future: We aren't going to watch that movie.", "nós não vamos assistir àquele filme."),
        ("Future: Are you going to do this?", "você vai fazer isso?"),
    ],
    "Infinitive": [
        ("Infinitive: She decided to study.", "ela decidiu estudar."),
        ("Infinitive: He promised to help.", "ele prometeu ajudar."),
        ("Infinitive: I want to help.", "eu quero ajudar."),
        ("Infinitive: I wanna leave.", "eu quero ir embora."),
        ("Infinitive: She needed to study more.", "ela precisava estudar mais."),
        ("Infinitive: David forgot to bring his notebook.", "David esqueceu de trazer seu caderno."),
        ("Infinitive: Stop to smoke.", "pare para fumar."),
        ("Infinitive: Stop smoking.", "pare de fumar."),
        ("Infinitive: Emma stopped talking.", "Emma parou de falar."),
        ("Infinitive: Emma stopped to talk.", "Emma parou para conversar."),
    ],
    "Demonstratives and Possessives": [
        ("Demonstratives and Possessives: That's my advice.", "Esse é o meu conselho."),
        ("Demonstratives and Possessives: I don't like that.", "Eu não gosto disso."),
        ("Demonstratives and Possessives: John's house.", "A casa do John."),
        ("Demonstratives and Possessives: I'm heading over to John's.", "Estou indo para a casa do John."),
        ("Demonstratives and Possessives: There is a new student in our class.", "Há um novo aluno na nossa turma."),
        ("Demonstratives and Possessives: Is there a bank near here?", "Há um banco por perto?"),
        ("Demonstratives and Possessives: There aren't any hotels in this area.", "Não há hotéis nesta área."),
        ("Demonstratives and Possessives: His car is very fast.", "O carro dele é muito rápido."),
        ("Demonstratives and Possessives: Her phone is charging.", "O celular dela está carregando."),
        ("Demonstratives and Possessives: They sold their old car.", "Eles venderam o carro antigo deles."),
        ("Demonstratives and Possessives: This book is mine.", "Este livro é meu."),
        ("Demonstratives and Possessives: The blue jacket is his.", "A jaqueta azul é dele."),
        ("Demonstratives and Possessives: The red bag is hers.", "A bolsa vermelha é dela."),
        ("Demonstratives and Possessives: These seats are theirs.", "Estes assentos são deles."),
        ("Demonstratives and Possessives: My phone is broken. Can I use yours?", "Meu celular está quebrado. Posso usar o seu?"),
        ("Demonstratives and Possessives: His answer was different from hers.", "A resposta dele foi diferente da dela."),
        ("Demonstratives and Possessives: Their choice was better.", "A escolha deles foi melhor."),
        ("Demonstratives and Possessives: The blue backpack is mine, the black one is his, and the red ones are theirs.", "A mochila azul é minha, a preta é dele e as vermelhas são deles."),
    ],
    "Object, Reflexive and Reciprocals": [
        ("Object, Reflexive and Reciprocals: Maria called them.", "Maria ligou para eles."),
        ("Object, Reflexive and Reciprocals: They invited us.", "Eles nos convidaram."),
        ("Object, Reflexive and Reciprocals: Actually, I like him.", "Na verdade, eu gosto dele."),
        ("Object, Reflexive and Reciprocals: They introduced themselves.", "Eles se apresentaram."),
        ("Object, Reflexive and Reciprocals: John and Mary helped each other.", "John e Mary ajudaram um ao outro."),
        ("Object, Reflexive and Reciprocals: John and Mary love themselves.", "John e Mary amam a si mesmos."),
        ("Object, Reflexive and Reciprocals: I met them at the airport.", "Eu os encontrei no aeroporto."),
        ("Object, Reflexive and Reciprocals: He hurt himself while playing soccer.", "Ele se machucou enquanto jogava futebol."),
        ("Object, Reflexive and Reciprocals: I blamed myself for the mistake.", "Eu me culpei pelo erro."),
        ("Object, Reflexive and Reciprocals: We have to believe in ourselves.", "Nós temos que acreditar em nós mesmos."),
    ],
    "Modals Pt. 1": [
        ("Modals Pt. 1: I can swim.", "Eu sei nadar."),
        ("Modals Pt. 1: I will study.", "Eu vou estudar."),
        ("Modals Pt. 1: She can't drive.", "Ela não sabe dirigir."),
        ("Modals Pt. 1: I cannot go.", "Eu não posso ir."),
        ("Modals Pt. 1: I might travel next year.", "Eu talvez viaje no próximo ano."),
        ("Modals Pt. 1: He might be tired.", "Ele pode estar cansado."),
        ("Modals Pt. 1: He might not agree.", "Ele pode não concordar."),
        ("Modals Pt. 1: You might like this movie.", "Você pode gostar deste filme."),
        ("Modals Pt. 1: She studies every day. She must be smart.", "Ela estuda todos os dias. Ela deve ser inteligente."),
        ("Modals Pt. 1: I must study.", "Eu preciso estudar."),
    ],
    "To x For": [
        ("To x For: Come to my house.", "Venha para a minha casa."),
        ("To x For: I'll do that for you.", "Eu farei isso por você."),
        ("To x For: Medicine for headaches.", "Remédio para dor de cabeça."),
        ("To x For: For how long are you going to be there?", "Por quanto tempo você vai ficar lá?"),
        ("To x For: I kept studying for 3 hours.", "Eu continuei estudando por 3 horas."),
        ("To x For: I left the message for John.", "Eu deixei o recado para o John."),
        ("To x For: I went home to watch a movie.", "Eu fui para casa para assistir a um filme."),
        ("To x For: I called you to ask a question.", "Eu liguei para você para fazer uma pergunta."),
        ("To x For: I bought a book for Mary.", "Eu comprei um livro para a Mary."),
        ("To x For: I gave the book to Mary.", "Eu dei o livro para a Mary."),
        ("To x For: This software is designed for small businesses.", "Este software foi desenvolvido para pequenas empresas."),
        ("To x For: Since I like Brazil, I wanna go there.", "Como eu gosto do Brasil, eu quero ir para lá."),
        ("To x For: I want to go to Brazil due to my interest in the country.", "Eu quero ir ao Brasil por causa do meu interesse pelo país."),
        ("To x For: As I like Brazil, I wanna go there.", "Como eu gosto do Brasil, eu quero ir para lá."),
    ],
    "Modals Pt. 2": [
        ("Modals Pt. 2: I would like that.", "Eu gostaria disso."),
        ("Modals Pt. 2: I would go to the party if I weren't so tired.", "Eu iria à festa se eu não estivesse tão cansado."),
        ("Modals Pt. 2: She would not be famous.", "Ela não seria famosa."),
        ("Modals Pt. 2: We would never do that.", "Nós nunca faríamos isso."),
        ("Modals Pt. 2: Wouldn't you care?", "Você não se importaria?"),
        ("Modals Pt. 2: I should be there.", "Eu deveria estar lá."),
        ("Modals Pt. 2: They should not listen to that.", "Eles não deveriam ouvir isso."),
        ("Modals Pt. 2: I shouldn't go.", "Eu não deveria ir."),
        ("Modals Pt. 2: She could do the work.", "Ela poderia fazer o trabalho."),
        ("Modals Pt. 2: When I was younger, I could run fast.", "Quando eu era mais jovem, eu conseguia correr rápido."),
        ("Modals Pt. 2: Could you help me?", "Você poderia me ajudar?"),
        ("Modals Pt. 2: Could they come with us?", "Eles poderiam vir conosco?"),
        ("Modals Pt. 2: May I come in?", "Posso entrar?"),
        ("Modals Pt. 2: She may be at home.", "Ela pode estar em casa."),
    ],
    "The Verb Get": [
        ("The Verb Get: He got a new job.", "Ele conseguiu um novo emprego."),
        ("The Verb Get: Did you get my email?", "Você recebeu meu e-mail?"),
        ("The Verb Get: Where did you get this jacket?", "Onde você conseguiu essa jaqueta?"),
        ("The Verb Get: Gotcha.", "Entendi."),
        ("The Verb Get: She got angry.", "Ela ficou brava."),
        ("The Verb Get: I'm getting tired.", "Estou ficando cansado."),
        ("The Verb Get: What time did you get home?", "Que horas você chegou em casa?"),
        ("The Verb Get: When I get home.", "Quando eu chegar em casa."),
        ("The Verb Get: I don't get it.", "Eu não entendo."),
        ("The Verb Get: Now I get it.", "Agora eu entendi."),
        ("The Verb Get: He got fired.", "Ele foi demitido."),
        ("The Verb Get: She is getting used to speaking English every day.", "Ela está se acostumando a falar inglês todos os dias."),
        ("The Verb Get: Do you get along with your neighbors?", "Você se dá bem com seus vizinhos?"),
        ("The Verb Get: You'll get over this mistake.", "Você vai superar esse erro."),
        ("The Verb Get: The thief got away before the police arrived.", "O ladrão fugiu antes que a polícia chegasse."),
        ("The Verb Get: Did you get it? Because I got it.", "Você entendeu? Porque eu entendi."),
        ("The Verb Get: Get dressed, hurry up, we have to leave.", "Vista-se, depressa, temos que sair."),
        ("The Verb Get: He got worse.", "Ele piorou."),
        ("The Verb Get: I am getting used to it.", "Estou me acostumando com isso."),
        ("The Verb Get: Get rid of these papers.", "Livre-se destes papéis."),
        ("The Verb Get: It was a difficult time, but I got through it.", "Foi um período difícil, mas eu consegui superar."),
    ],
    "In, On and At": [
        ("In, On and At: My office is on the second floor.", "Meu escritório fica no segundo andar."),
        ("In, On and At: She arrived at midnight.", "Ela chegou à meia-noite."),
        ("In, On and At: I have English class on Monday.", "Eu tenho aula de inglês na segunda-feira."),
        ("In, On and At: Her birthday is on July 15th.", "O aniversário dela é em 15 de julho."),
        ("In, On and At: I was born in 2003.", "Eu nasci em 2003."),
        ("In, On and At: He moved here in the 1990s.", "Ele se mudou para cá na década de 1990."),
        ("In, On and At: They're at the airport.", "Eles estão no aeroporto."),
        ("In, On and At: Meet me at the bus stop.", "Encontre-me no ponto de ônibus."),
        ("In, On and At: The cat is on the roof.", "O gato está no telhado."),
        ("In, On and At: I live on Main Street.", "Eu moro na Main Street."),
        ("In, On and At: I'm on the bus.", "Eu estou no ônibus."),
        ("In, On and At: I'm in the car.", "Eu estou no carro."),
        ("In, On and At: They live in Brazil.", "Eles moram no Brasil."),
        ("In, On and At: There's money in my pocket.", "Há dinheiro no meu bolso."),
    ],
    "Comparatives and Superlatives": [
        ("Comparatives and Superlatives: My car is faster than yours.", "Meu carro é mais rápido que o seu."),
        ("Comparatives and Superlatives: This book is more interesting than that one.", "Este livro é mais interessante do que aquele."),
        ("Comparatives and Superlatives: Today is colder than yesterday.", "Hoje está mais frio do que ontem."),
        ("Comparatives and Superlatives: This hotel is more expensive than that one.", "Este hotel é mais caro do que aquele."),
        ("Comparatives and Superlatives: She is as tall as her sister.", "Ela é tão alta quanto a irmã dela."),
        ("Comparatives and Superlatives: This phone is as expensive as mine.", "Este celular é tão caro quanto o meu."),
        ("Comparatives and Superlatives: He runs as fast as me.", "Ele corre tão rápido quanto eu."),
        ("Comparatives and Superlatives: This car is not as fast as that one.", "Este carro não é tão rápido quanto aquele."),
        ("Comparatives and Superlatives: My English is not as good as yours.", "Meu inglês não é tão bom quanto o seu."),
        ("Comparatives and Superlatives: The exam was not as difficult as I expected.", "A prova não foi tão difícil quanto eu esperava."),
        ("Comparatives and Superlatives: The weather is slightly warmer today.", "O tempo está um pouco mais quente hoje."),
        ("Comparatives and Superlatives: The second test was way easier.", "A segunda prova foi muito mais fácil."),
        ("Comparatives and Superlatives: This car is far better than the old one.", "Este carro é muito melhor do que o antigo."),
        ("Comparatives and Superlatives: Today is even colder than yesterday.", "Hoje está ainda mais frio do que ontem."),
        ("Comparatives and Superlatives: This is the most beautiful beach in Brazil.", "Esta é a praia mais bonita do Brasil."),
        ("Comparatives and Superlatives: It was the best day of my life.", "Foi o melhor dia da minha vida."),
        ("Comparatives and Superlatives: The least interesting subject.", "A matéria menos interessante."),
        ("Comparatives and Superlatives: She is the tallest student in the class.", "Ela é a aluna mais alta da turma."),
        ("Comparatives and Superlatives: The strongest one.", "O mais forte."),
        ("Comparatives and Superlatives: That's the cheapest one.", "Esse é o mais barato."),
        ("Comparatives and Superlatives: My car is less expensive than yours.", "Meu carro é menos caro do que o seu."),
    ],
    "Participle (Perfect)": [
        ("Participle (Perfect): I have gone home.", "Eu já fui para casa."),
        ("Participle (Perfect): She has seen this movie.", "Ela já viu esse filme."),
        ("Participle (Perfect): We have eaten already.", "Nós já comemos."),
        ("Participle (Perfect): He has done his homework.", "Ele já fez o dever de casa."),
        ("Participle (Perfect): I have written a letter.", "Eu já escrevi uma carta."),
        ("Participle (Perfect): They have taken a picture.", "Eles já tiraram uma foto."),
        ("Participle (Perfect): She has given me a gift.", "Ela já me deu um presente."),
        ("Participle (Perfect): We have spoken to him.", "Nós já falamos com ele."),
        ("Participle (Perfect): He has broken the glass.", "Ele já quebrou o copo."),
        ("Participle (Perfect): I have chosen a new one.", "Eu já escolhi um novo."),
        ("Participle (Perfect): They have driven all day.", "Eles dirigiram o dia todo."),
        ("Participle (Perfect): She has forgotten my name.", "Ela já esqueceu meu nome."),
        ("Participle (Perfect): We have known him for years.", "Nós o conhecemos há anos."),
        ("Participle (Perfect): He has begun the lesson.", "Ele já começou a aula."),
        ("Participle (Perfect): I have drunk some water.", "Eu já bebi um pouco de água."),
        ("Participle (Perfect): She had gone home.", "Ela já tinha ido para casa."),
        ("Participle (Perfect): We had seen the movie before.", "Nós já tínhamos visto o filme antes."),
        ("Participle (Perfect): He had done his homework.", "Ele já tinha feito o dever de casa."),
    ],
}


def die(msg: str):
    print(f"ERRO: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    if not PROFESSOR_EMAIL or not PROFESSOR_PASSWORD:
        die("Defina PROFESSOR_EMAIL e PROFESSOR_PASSWORD como variáveis de ambiente.")

    session = requests.Session()

    # 1. Login
    resp = session.post(
        f"{API_BASE_URL}/auth/login",
        data={"username": PROFESSOR_EMAIL, "password": PROFESSOR_PASSWORD},
    )
    if resp.status_code != 200:
        die(f"Falha no login ({resp.status_code}): {resp.text}")
    token = resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})

    # 2. Alunos aprovados
    resp = session.get(f"{API_BASE_URL}/admin/students")
    if resp.status_code != 200:
        die(f"Falha ao buscar alunos ({resp.status_code}): {resp.text}")
    students = [s for s in resp.json() if s["is_approved"]]
    if TARGET_STUDENT_NAMES is not None:
        students = [s for s in students if s["name"] in TARGET_STUDENT_NAMES]
    if not students:
        die("Nenhum aluno aprovado encontrado (ou nenhum bate com TARGET_STUDENT_NAMES).")
    student_ids = [s["id"] for s in students]
    print(f"Alunos alvo: {', '.join(s['name'] for s in students)}")

    # 3. Apaga os flashcards existentes dos decks que este script vai
    # recriar, para os alunos-alvo.
    #
    # - Modo "enviar para todos" (TARGET_STUDENT_NAMES = None): apaga TODOS
    #   os flashcards cadastrados, como antes.
    # - Modo restrito (ex.: TARGET_STUDENT_NAMES = ["Daniel", "Andrielle"]):
    #   NÃO apaga tudo (não mexe no vocabulário de outros alunos). Em vez
    #   disso, apaga só os decks antigos (pelo nome, batendo com as chaves de
    #   DECKS) que já tinham sido enviados exclusivamente para os alunos-alvo
    #   — isso evita que rodar o script de novo (ex.: depois de adicionar o
    #   prefixo do tema no front) deixe as versões antiga e nova duplicadas
    #   para o mesmo aluno. Um deck que também foi enviado para outro aluno
    #   fora da lista é deixado intacto, por segurança.
    if TARGET_STUDENT_NAMES is None:
        resp = session.get(f"{API_BASE_URL}/flashcards")
        if resp.status_code != 200:
            die(f"Falha ao listar flashcards existentes ({resp.status_code}): {resp.text}")
        existing = resp.json()
        print(f"Excluindo {len(existing)} flashcard(s) existente(s)...")
        for card in existing:
            r = session.delete(f"{API_BASE_URL}/flashcards/{card['id']}")
            if r.status_code not in (200, 204):
                print(f"  aviso: falha ao excluir flashcard {card['id']}: {r.status_code} {r.text}")
    else:
        target_id_set = set(student_ids)
        resp = session.get(f"{API_BASE_URL}/flashcards/batches")
        if resp.status_code != 200:
            die(f"Falha ao listar decks existentes ({resp.status_code}): {resp.text}")
        batches = resp.json()

        to_replace = [
            b for b in batches
            if b["batch_name"] in DECKS
            and {s["id"] for s in b["students"]} <= target_id_set
            and b["students"]
        ]
        if not to_replace:
            print("Nenhum deck antigo (só dos alunos-alvo) pra substituir — seguindo direto pra criação.")
        for batch in to_replace:
            print(f"  Substituindo deck antigo '{batch['batch_name']}' "
                  f"(id {batch['batch_id']}, {len(batch['cards'])} card(s))...")
            for card in batch["cards"]:
                r = session.delete(f"{API_BASE_URL}/flashcards/{card['id']}")
                if r.status_code not in (200, 204):
                    print(f"    aviso: falha ao excluir flashcard {card['id']}: {r.status_code} {r.text}")
            r = session.delete(f"{API_BASE_URL}/flashcards/batches/{batch['batch_id']}")
            if r.status_code not in (200, 204):
                print(f"    aviso: falha ao excluir o registro do deck {batch['batch_id']}: {r.status_code} {r.text}")

    # 4. Cria um deck por tópico, já enviado aos alunos
    total_cards = 0
    for deck_name, pairs in DECKS.items():
        cards = [{"front": front, "back": back} for front, back in pairs]
        payload = {"name": deck_name, "cards": cards, "student_ids": student_ids}
        r = session.post(f"{API_BASE_URL}/flashcards/batch", json=payload)
        if r.status_code != 201:
            print(f"  erro ao criar deck '{deck_name}': {r.status_code} {r.text}")
            continue
        total_cards += len(cards)
        print(f"  ✓ deck '{deck_name}' criado com {len(cards)} flashcard(s).")

    print(f"\nConcluído: {len(DECKS)} deck(s), {total_cards} flashcard(s) no total, "
          f"enviados para {len(students)} aluno(s) e disponíveis na aba Histórico.")


if __name__ == "__main__":
    main()
