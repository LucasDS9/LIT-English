"""
Script de seed: substitui TODOS os flashcards existentes pelos decks abaixo
(extraídos do documento de vocabulário do professor) e já envia cada deck,
como um bloco no Histórico, para todos os alunos aprovados no momento em
que o script roda.

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_flashcards_from_doc.py

O script:
  1. Faz login como professor.
  2. Busca a lista de alunos aprovados no momento (dinâmico — não é uma
     lista fixa de nomes, então funciona em qualquer ambiente/banco).
  3. Apaga TODOS os flashcards atualmente cadastrados (e, por cascata no
     banco, os vínculos, o progresso de revisão e os decks antigos).
  4. Cria um deck (bloco no Histórico) por tópico gramatical, com os
     flashcards abaixo, já atribuído a todos os alunos aprovados.

Se quiser enviar só para alunos específicos, edite a lista `TARGET_STUDENT_NAMES`
mais abaixo (deixe None para enviar a todos os aprovados, que é o padrão).
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# Se quiser restringir o envio a alunos específicos, liste os nomes exatos
# (como aparecem em /admin/students) aqui. None = todos os alunos aprovados.
TARGET_STUDENT_NAMES = ["aluno"]


# ---------------------------------------------------------------------------
# Decks extraídos do documento (front = inglês, back = português)
# ---------------------------------------------------------------------------
DECKS = {
    "Past": [
        ("They were busy", "eles estavam ocupados"),
        ("It was cold", "estava frio"),
        ("I needed help", "eu precisava de ajuda"),
        ("We bought a lot of things", "nós compramos várias coisas"),
        ("I went to school yesterday", "eu fui para a escola ontem"),
        ("My brother was not there", "meu irmão não estava lá"),
        ("It wasn't difficult", "não foi difícil"),
        ("I did not watch TV", "eu não assisti TV"),
    ],
    "Future": [
        ("They will be there.", "eles estarão lá."),
        ("We will try.", "nós tentaremos."),
        ("I'm about to leave.", "estou prestes a sair."),
        ("I will not give up.", "eu não vou desistir."),
        ("We won't be available.", "nós não estaremos disponíveis."),
        ("You won't believe what just happened.", "você não vai acreditar no que acabou de acontecer."),
        ("We are gonna stay.", "nós vamos ficar."),
        ("We are going to John's house.", "nós vamos para a casa do John."),
        ("We aren't going to watch that movie.", "nós não vamos assistir àquele filme."),
        ("Are you going to do this?", "você vai fazer isso?"),
    ],
    "Infinitive": [
        ("She decided to study.", "ela decidiu estudar."),
        ("He promised to help.", "ele prometeu ajudar."),
        ("I want to help.", "eu quero ajudar."),
        ("I wanna leave.", "eu quero ir embora."),
        ("She needed to study more.", "ela precisava estudar mais."),
        ("David forgot to bring his notebook.", "David esqueceu de trazer seu caderno."),
        ("Stop to smoke.", "pare para fumar."),
        ("Stop smoking.", "pare de fumar."),
        ("Emma stopped talking.", "Emma parou de falar."),
        ("Emma stopped to talk.", "Emma parou para conversar."),
    ],
    "Demonstratives and Possessives": [
        ("That's my advice.", "Esse é o meu conselho."),
        ("I don't like that.", "Eu não gosto disso."),
        ("John's house.", "A casa do John."),
        ("I'm heading over to John's.", "Estou indo para a casa do John."),
        ("There is a new student in our class.", "Há um novo aluno na nossa turma."),
        ("Is there a bank near here?", "Há um banco por perto?"),
        ("There aren't any hotels in this area.", "Não há hotéis nesta área."),
        ("His car is very fast.", "O carro dele é muito rápido."),
        ("Her phone is charging.", "O celular dela está carregando."),
        ("They sold their old car.", "Eles venderam o carro antigo deles."),
        ("This book is mine.", "Este livro é meu."),
        ("The blue jacket is his.", "A jaqueta azul é dele."),
        ("The red bag is hers.", "A bolsa vermelha é dela."),
        ("These seats are theirs.", "Estes assentos são deles."),
        ("My phone is broken. Can I use yours?", "Meu celular está quebrado. Posso usar o seu?"),
        ("His answer was different from hers.", "A resposta dele foi diferente da dela."),
        ("Their choice was better.", "A escolha deles foi melhor."),
        (
            "The blue backpack is mine, the black one is his, and the red ones are theirs.",
            "A mochila azul é minha, a preta é dele e as vermelhas são deles.",
        ),
    ],
    "Object, Reflexive and Reciprocals": [
        ("Maria called them.", "Maria ligou para eles."),
        ("They invited us.", "Eles nos convidaram."),
        ("Actually, I like him.", "Na verdade, eu gosto dele."),
        ("They introduced themselves.", "Eles se apresentaram."),
        ("John and Mary helped each other.", "John e Mary ajudaram um ao outro."),
        ("John and Mary love themselves.", "John e Mary amam a si mesmos."),
        ("I met them at the airport.", "Eu os encontrei no aeroporto."),
        ("He hurt himself while playing soccer.", "Ele se machucou enquanto jogava futebol."),
        ("I blamed myself for the mistake.", "Eu me culpei pelo erro."),
        ("We have to believe in ourselves.", "Nós temos que acreditar em nós mesmos."),
    ],
    "Modals Pt. 1": [
        ("I can swim.", "Eu sei nadar."),
        ("I will study.", "Eu vou estudar."),
        ("She can't drive.", "Ela não sabe dirigir."),
        ("I cannot go.", "Eu não posso ir."),
        ("I might travel next year.", "Eu talvez viaje no próximo ano."),
        ("He might be tired.", "Ele pode estar cansado."),
        ("He might not agree.", "Ele pode não concordar."),
        ("You might like this movie.", "Você pode gostar deste filme."),
        ("She studies every day. She must be smart.", "Ela estuda todos os dias. Ela deve ser inteligente."),
        ("I must study.", "Eu preciso estudar."),
    ],
    "To x For": [
        ("Come to my house.", "Venha para a minha casa."),
        ("I'll do that for you.", "Eu farei isso por você."),
        ("Medicine for headaches.", "Remédio para dor de cabeça."),
        ("For how long are you going to be there?", "Por quanto tempo você vai ficar lá?"),
        ("I kept studying for 3 hours.", "Eu continuei estudando por 3 horas."),
        ("I left the message for John.", "Eu deixei o recado para o John."),
        ("I went home to watch a movie.", "Eu fui para casa para assistir a um filme."),
        ("I called you to ask a question.", "Eu liguei para você para fazer uma pergunta."),
        ("I bought a book for Mary.", "Eu comprei um livro para a Mary."),
        ("I gave the book to Mary.", "Eu dei o livro para a Mary."),
        ("This software is designed for small businesses.", "Este software foi desenvolvido para pequenas empresas."),
        ("Since I like Brazil, I wanna go there.", "Como eu gosto do Brasil, eu quero ir para lá."),
        ("I want to go to Brazil due to my interest in the country.", "Eu quero ir ao Brasil por causa do meu interesse pelo país."),
        ("As I like Brazil, I wanna go there.", "Como eu gosto do Brasil, eu quero ir para lá."),
    ],
    "Modals Pt. 2": [
        ("I would like that.", "Eu gostaria disso."),
        ("I would go to the party if I weren't so tired.", "Eu iria à festa se eu não estivesse tão cansado."),
        ("She would not be famous.", "Ela não seria famosa."),
        ("We would never do that.", "Nós nunca faríamos isso."),
        ("Wouldn't you care?", "Você não se importaria?"),
        ("I should be there.", "Eu deveria estar lá."),
        ("They should not listen to that.", "Eles não deveriam ouvir isso."),
        ("I shouldn't go.", "Eu não deveria ir."),
        ("She could do the work.", "Ela poderia fazer o trabalho."),
        ("When I was younger, I could run fast.", "Quando eu era mais jovem, eu conseguia correr rápido."),
        ("Could you help me?", "Você poderia me ajudar?"),
        ("Could they come with us?", "Eles poderiam vir conosco?"),
        ("May I come in?", "Posso entrar?"),
        ("She may be at home.", "Ela pode estar em casa."),
    ],
    "The Verb Get": [
        ("He got a new job.", "Ele conseguiu um novo emprego."),
        ("Did you get my email?", "Você recebeu meu e-mail?"),
        ("Where did you get this jacket?", "Onde você conseguiu essa jaqueta?"),
        ("Gotcha.", "Entendi."),
        ("She got angry.", "Ela ficou brava."),
        ("I'm getting tired.", "Estou ficando cansado."),
        ("What time did you get home?", "Que horas você chegou em casa?"),
        ("When I get home.", "Quando eu chegar em casa."),
        ("I don't get it.", "Eu não entendo."),
        ("Now I get it.", "Agora eu entendi."),
        ("He got fired.", "Ele foi demitido."),
        ("She is getting used to speaking English every day.", "Ela está se acostumando a falar inglês todos os dias."),
        ("Do you get along with your neighbors?", "Você se dá bem com seus vizinhos?"),
        ("You'll get over this mistake.", "Você vai superar esse erro."),
        ("The thief got away before the police arrived.", "O ladrão fugiu antes que a polícia chegasse."),
        ("Did you get it? Because I got it.", "Você entendeu? Porque eu entendi."),
        ("Get dressed, hurry up, we have to leave.", "Vista-se, depressa, temos que sair."),
        ("He got worse.", "Ele piorou."),
        ("I am getting used to it.", "Estou me acostumando com isso."),
        ("Get rid of these papers.", "Livre-se destes papéis."),
        ("It was a difficult time, but I got through it.", "Foi um período difícil, mas eu consegui superar."),
    ],
    "In, On and At": [
        ("My office is on the second floor.", "Meu escritório fica no segundo andar."),
        ("She arrived at midnight.", "Ela chegou à meia-noite."),
        ("I have English class on Monday.", "Eu tenho aula de inglês na segunda-feira."),
        ("Her birthday is on July 15th.", "O aniversário dela é em 15 de julho."),
        ("I was born in 2003.", "Eu nasci em 2003."),
        ("He moved here in the 1990s.", "Ele se mudou para cá na década de 1990."),
        ("They're at the airport.", "Eles estão no aeroporto."),
        ("Meet me at the bus stop.", "Encontre-me no ponto de ônibus."),
        ("The cat is on the roof.", "O gato está no telhado."),
        ("I live on Main Street.", "Eu moro na Main Street."),
        ("I'm on the bus.", "Eu estou no ônibus."),
        ("I'm in the car.", "Eu estou no carro."),
        ("They live in Brazil.", "Eles moram no Brasil."),
        ("There's money in my pocket.", "Há dinheiro no meu bolso."),
    ],
    "Comparatives and Superlatives": [
        ("My car is faster than yours.", "Meu carro é mais rápido que o seu."),
        ("This book is more interesting than that one.", "Este livro é mais interessante do que aquele."),
        ("Today is colder than yesterday.", "Hoje está mais frio do que ontem."),
        ("This hotel is more expensive than that one.", "Este hotel é mais caro do que aquele."),
        ("She is as tall as her sister.", "Ela é tão alta quanto a irmã dela."),
        ("This phone is as expensive as mine.", "Este celular é tão caro quanto o meu."),
        ("He runs as fast as me.", "Ele corre tão rápido quanto eu."),
        ("This car is not as fast as that one.", "Este carro não é tão rápido quanto aquele."),
        ("My English is not as good as yours.", "Meu inglês não é tão bom quanto o seu."),
        ("The exam was not as difficult as I expected.", "A prova não foi tão difícil quanto eu esperava."),
        ("The weather is slightly warmer today.", "O tempo está um pouco mais quente hoje."),
        ("The second test was way easier.", "A segunda prova foi muito mais fácil."),
        ("This car is far better than the old one.", "Este carro é muito melhor do que o antigo."),
        ("Today is even colder than yesterday.", "Hoje está ainda mais frio do que ontem."),
        ("This is the most beautiful beach in Brazil.", "Esta é a praia mais bonita do Brasil."),
        ("It was the best day of my life.", "Foi o melhor dia da minha vida."),
        ("The least interesting subject.", "A matéria menos interessante."),
        ("She is the tallest student in the class.", "Ela é a aluna mais alta da turma."),
        ("The strongest one.", "O mais forte."),
        ("That's the cheapest one.", "Esse é o mais barato."),
        ("My car is less expensive than yours.", "Meu carro é menos caro do que o seu."),
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

    # 3. Apaga todos os flashcards existentes — SÓ no modo "enviar para todos"
    # (TARGET_STUDENT_NAMES = None). Quando você restringe a alunos
    # específicos (ex.: uma conta de teste), isso é claramente um teste, e
    # apagar o vocabulário de todo mundo por causa de um teste seria
    # perigoso — então o script pula a exclusão nesse caso.
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
        print("TARGET_STUDENT_NAMES definido — pulando a exclusão dos flashcards "
              "existentes (modo de teste, não mexe no que já está em uso pelos outros alunos).")

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
