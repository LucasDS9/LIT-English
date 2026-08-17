"""
Script: apaga do banco os VocabWord da Parte 2 (Chunks e verbos
essenciais — `category == "verbos"`, língua "ingles"), que foram
enviados por versões antigas de seed_vocab_words.py antes da Parte 2
ser removida do arquivo.

A Parte 1 (`category == "saudacoes"`) NÃO é afetada.

Isso apaga o VocabWord em si (VocabWordProgress associado também é
removido, via cascade no backend). NÃO mexe no modelo `Flashcard`
(sistema de revisão SM-2 com front/back) — esse é um sistema
totalmente separado, sem conceito de "parte".

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/delete_vocab_words_parte2.py

ATENÇÃO: ação destrutiva e IRREVERSÍVEL, afeta todos os alunos do
curso normal de inglês. O script pede confirmação digitada antes de
apagar. Para pular a confirmação (ex.: CI), defina CONFIRM=yes.
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")
CONFIRM = os.environ.get("CONFIRM", "").strip().lower()

LANGUAGE = "ingles"
CATEGORY_TO_DELETE = "verbos"  # Parte 2


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

    print("Buscando palavras cadastradas...")
    resp = requests.get(f"{API_BASE_URL}/vocab-words", headers=headers)
    resp.raise_for_status()
    all_words = resp.json()

    to_delete = [
        w for w in all_words
        if w.get("language", "").strip().lower() == LANGUAGE
        and w.get("category", "saudacoes").strip().lower() == CATEGORY_TO_DELETE
    ]

    if not to_delete:
        print(f"Nenhuma palavra com category='{CATEGORY_TO_DELETE}' e language='{LANGUAGE}' encontrada. Nada a fazer.")
        return

    print(f"Encontradas {len(to_delete)} palavra(s) da Parte 2 (de {len(all_words)} no total).")

    if CONFIRM != "yes":
        answer = input(
            f"Isso vai APAGAR PERMANENTEMENTE {len(to_delete)} palavra(s) da Parte 2 "
            f"(category='{CATEGORY_TO_DELETE}') em {API_BASE_URL}, pra todos os alunos. "
            f"A Parte 1 (category='saudacoes') NÃO será tocada. Digite 'apagar' para confirmar: "
        )
        if answer.strip().lower() != "apagar":
            print("Cancelado. Nada foi apagado.")
            sys.exit(0)

    deleted = 0
    failed = 0
    for word in to_delete:
        word_id = word["id"]
        del_resp = requests.delete(f"{API_BASE_URL}/vocab-words/{word_id}", headers=headers)
        if del_resp.status_code == 204:
            deleted += 1
            print(f"Apagado: id={word_id} word={word.get('word')!r}")
        else:
            failed += 1
            print(f"Falha ao apagar id={word_id}: {del_resp.status_code} {del_resp.text}")

    print(f"Concluído. Apagados: {deleted} | Falhas: {failed}")


if __name__ == "__main__":
    main()
