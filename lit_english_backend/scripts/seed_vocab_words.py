"""
Script de seed: cria a palavra de exemplo da tela "Aprender" (o card "learn"
usado no mockup) via API, já atribuída aos alunos aprovados.

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_vocab_words.py

Mais palavras podem ser adicionadas depois — basta acrescentar itens na
lista WORDS abaixo (ou criar um outro script), sem duplicar nada, já que o
professor também pode cadastrar pelo painel quando essa tela existir lá.
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# Se quiser restringir o envio a alunos específicos, liste os nomes exatos
# (como aparecem em /admin/students) aqui. None = todos os alunos aprovados.
TARGET_STUDENT_NAMES = None

# ---------------------------------------------------------------------------
# Palavra(s) de exemplo — mesma da tela mostrada no mockup do "Aprender"
# ---------------------------------------------------------------------------
WORDS = [
    {
        "word": "learn",
        "part_of_speech": "verbo",
        "translation": "aprender",
        "example_sentence": "I will learn English.",
        "distractors": ["melhorar", "falar", "praticar"],
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

    print("Buscando alunos aprovados...")
    students_resp = requests.get(f"{API_BASE_URL}/admin/students", headers=headers)
    students_resp.raise_for_status()
    students = students_resp.json()

    if TARGET_STUDENT_NAMES:
        students = [s for s in students if s["name"] in TARGET_STUDENT_NAMES]

    student_ids = [s["id"] for s in students]
    if not student_ids:
        print("Nenhum aluno encontrado para atribuir as palavras. Abortando.")
        sys.exit(1)

    print(f"Atribuindo para {len(student_ids)} aluno(s): {[s['name'] for s in students]}")

    for item in WORDS:
        payload = {**item, "student_ids": student_ids}
        resp = requests.post(f"{API_BASE_URL}/vocab-words", json=payload, headers=headers)
        if resp.status_code >= 400:
            print(f"Falha ao criar '{item['word']}': {resp.status_code} {resp.text}")
            continue
        created = resp.json()
        print(f"Criado: '{created['word']}' (id={created['id']}) -> {created['translation']}")

    print("Concluído.")


if __name__ == "__main__":
    main()
