"""
Script de seed: cria palavras da tela "Aprender" via API. Como o campo
`student_ids` agora é OPCIONAL (ver VocabWordCreate/create_vocab_word), não
enviamos ele aqui de propósito — a API atribui a palavra automaticamente a
todos os alunos aprovados no momento, e o backend garante que qualquer
aluno aprovado depois (em admin.approve_student) também receba as mesmas
palavras. Ou seja: a partir daqui, as palavras cadastradas aqui ficam
nativas para todo aluno que cria conta e é aprovado, sem precisar
selecionar aluno por aluno.

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_vocab_words.py

Este arquivo contém, por enquanto, só as 5 primeiras palavras (saudações)
como TESTE. As demais (o restante das saudações + a tabela de expressões
comuns como "Yes", "Thanks", "Sorry" etc.) podem ser acrescentadas depois
na lista WORDS abaixo, seguindo o mesmo formato — sem duplicar nada, já
que basta rodar o script de novo com os itens novos.
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# ---------------------------------------------------------------------------
# TESTE: as 5 primeiras saudações da tabela. Estas usam `tip` (a coluna
# "Quando usamos" da tabela) no lugar de `example_sentence`, já que
# saudações não têm uma frase de exemplo — é assim que o card mostra a
# dica logo abaixo da palavra principal.
#
# A tradução certa (`translation`) foi escolhida dentre as 4 alternativas
# da tabela original (a que corresponde ao uso descrito); as outras 3
# alternativas de cada linha viram `distractors`.
# ---------------------------------------------------------------------------
WORDS = [
    {
        "word": "Hi",
        "part_of_speech": "saudação",
        "tip": "Saudação informal e muito comum.",
        "translation": "Olá",
        "distractors": ["Até mais", "Boa noite", "Adeus"],
    },
    {
        "word": "Hello",
        "part_of_speech": "saudação",
        "tip": "Saudação geral e neutra.",
        "translation": "Olá",
        "distractors": ["Tchau", "Até amanhã", "Se cuida"],
    },
    {
        "word": "Good morning",
        "part_of_speech": "saudação",
        "tip": "Para cumprimentar alguém pela manhã.",
        "translation": "Bom dia",
        "distractors": ["Boa tarde", "Boa noite", "Até mais"],
    },
    {
        "word": "Good afternoon",
        "part_of_speech": "saudação",
        "tip": "Para cumprimentar alguém à tarde.",
        "translation": "Boa tarde",
        "distractors": ["Boa noite", "Até mais", "Bom dia"],
    },
    {
        "word": "Good evening",
        "part_of_speech": "saudação",
        "tip": "Para cumprimentar alguém à noite.",
        "translation": "Boa noite",
        "distractors": ["Boa tarde", "Bom dia", "Até mais"],
    },
]


def main():
    if not PROFESSOR_EMAIL or not PROFESSOR_PASSWORD:
        print("Defina PROFESSOR_EMAIL e PROFESSOR_PASSWORD nas variáveis de ambiente.")
        sys.exit(1)

    print(f"Fazendo login em {API_BASE_URL}...")
    login_resp = requests.post(
        f"{API_BASE_URL}/auth/login",
        data={"username": PROFESSOR_EMAIL, "password": PROFESSOR_PASSWORD},
    )
    login_resp.raise_for_status()
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for item in WORDS:
        # Sem `student_ids`: a API atribui automaticamente a todos os
        # alunos aprovados agora (e aos aprovados depois).
        resp = requests.post(f"{API_BASE_URL}/vocab-words", json=item, headers=headers)
        if resp.status_code >= 400:
            print(f"Falha ao criar '{item['word']}': {resp.status_code} {resp.text}")
            continue
        created = resp.json()
        n_students = len(created.get("students", []))
        print(f"Criado: '{created['word']}' (id={created['id']}) -> {created['translation']} "
              f"[{n_students} aluno(s) aprovado(s) agora]")

    print("Concluído.")


if __name__ == "__main__":
    main()
