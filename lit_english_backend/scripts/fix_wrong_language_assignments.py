"""
Script de limpeza: remove, da tela "Aprender", as atribuições de palavras
cuja língua NÃO bate com a língua-alvo do aluno — o caso relatado foi um
aluno de Acesso Especial (target_language="italiano") que ficou com
palavras de "ingles" atribuídas (isso pode acontecer se o aluno foi
aprovado ANTES de ter o Acesso Especial/target_language configurado
corretamente, já que a atribuição automática roda no momento da aprovação
— ver admin.approve_student).

O que o script faz, pra cada palavra cadastrada (GET /vocab-words):
  1. Olha a língua da palavra (`language`, ex.: "ingles" ou "italiano").
  2. Olha a língua-alvo de cada aluno atribuído a ela (via GET
     /admin/students, mesma regra do student_language() do backend:
     access_type=="especial" com target_language preenchido -> essa
     língua; senão -> "ingles").
  3. Se algum aluno atribuído não bate com a língua da palavra, ele é
     removido dessa atribuição (PUT /vocab-words/{id} com a lista de
     alunos corrigida — os outros alunos, que estão certos, permanecem).

NÃO apaga a palavra, nem o aluno, nem toca em palavras que já estão
corretas — só desfaz atribuições erradas. É seguro rodar mais de uma vez:
se não houver nada pra corrigir, o script não faz nenhuma chamada de
escrita.

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/fix_wrong_language_assignments.py

Use --dry-run para só listar o que seria corrigido, sem alterar nada:
    python scripts/fix_wrong_language_assignments.py --dry-run
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

DRY_RUN = "--dry-run" in sys.argv


def _expected_language(student: dict) -> str:
    """Mesma regra do student_language() em app/routers/vocab_words.py."""
    if student.get("access_type") == "especial" and student.get("target_language"):
        return student["target_language"].strip().lower()
    return "ingles"


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

    print("Buscando alunos...")
    students_resp = requests.get(f"{API_BASE_URL}/admin/students", headers=headers)
    students_resp.raise_for_status()
    expected_language_by_id = {
        s["id"]: _expected_language(s) for s in students_resp.json()
    }

    print("Buscando palavras cadastradas...")
    words_resp = requests.get(f"{API_BASE_URL}/vocab-words", headers=headers)
    words_resp.raise_for_status()
    words = words_resp.json()

    total_fixed_words = 0
    total_removed_assignments = 0

    for word in words:
        word_language = word["language"].strip().lower()
        correct_ids = []
        wrong_students = []

        for s in word.get("students", []):
            expected = expected_language_by_id.get(s["id"], "ingles")
            if expected == word_language:
                correct_ids.append(s["id"])
            else:
                wrong_students.append((s["id"], s["name"], expected))

        if not wrong_students:
            continue

        names = ", ".join(f"{name} (é de {lang})" for _id, name, lang in wrong_students)
        print(
            f"'{word['word']}' [{word_language}] (id={word['id']}) está atribuída a "
            f"aluno(s) de língua errada: {names}"
        )

        if not correct_ids:
            print(
                f"  -> AVISO: depois de remover, essa palavra ficaria sem nenhum aluno "
                f"correto atribuído. Pulei essa por segurança — confira manualmente."
            )
            continue

        if DRY_RUN:
            print(f"  -> [dry-run] removeria {len(wrong_students)} atribuição(ões).")
        else:
            resp = requests.put(
                f"{API_BASE_URL}/vocab-words/{word['id']}",
                json={"student_ids": correct_ids},
                headers=headers,
            )
            if resp.status_code >= 400:
                print(f"  -> Falha ao corrigir: {resp.status_code} {resp.text}")
                continue
            print(f"  -> Corrigido: removida(s) {len(wrong_students)} atribuição(ões) errada(s).")

        total_fixed_words += 1
        total_removed_assignments += len(wrong_students)

    if total_fixed_words == 0:
        print("Nada para corrigir — todas as atribuições já batem com a língua de cada aluno.")
    else:
        modo = "(dry-run, nada foi alterado)" if DRY_RUN else ""
        print(
            f"Concluído {modo}. Palavras corrigidas: {total_fixed_words} | "
            f"Atribuições removidas: {total_removed_assignments}"
        )


if __name__ == "__main__":
    main()
