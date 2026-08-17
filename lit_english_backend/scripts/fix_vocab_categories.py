"""
Corrige SOMENTE a categoria das palavras já cadastradas em "Aprender".

Use este script quando a base já possui as palavras, mas elas aparecem
todas dentro de "Saudações". Ele usa exatamente o `WORDS` de
seed_vocab_words.py como fonte de verdade e não altera tradução, distratores,
progresso ou atribuição dos alunos.

Uso:
    cd lit_english_backend
    PROFESSOR_EMAIL="..." PROFESSOR_PASSWORD="..." \
    python scripts/fix_vocab_categories.py
"""
import os
import sys
from collections import Counter

import requests

from seed_vocab_words import (
    API_BASE_URL,
    PROFESSOR_EMAIL,
    PROFESSOR_PASSWORD,
    LANGUAGE,
    WORDS,
    CATEGORY_ORDER,
)


def fetch_existing(base_url, headers):
    response = requests.get(f"{base_url}/vocab-words", headers=headers)
    response.raise_for_status()
    return response.json()


def main():
    if not PROFESSOR_EMAIL or not PROFESSOR_PASSWORD:
        print("Defina PROFESSOR_EMAIL e PROFESSOR_PASSWORD nas variáveis de ambiente.")
        sys.exit(1)

    login = requests.post(
        f"{API_BASE_URL}/auth/login",
        data={"username": PROFESSOR_EMAIL, "password": PROFESSOR_PASSWORD},
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    existing = fetch_existing(API_BASE_URL, headers)

    # A chave inclui tradução porque algumas palavras/expressões podem ter
    # mais de um sentido no banco.
    by_key = {
        (
            item["word"].strip().lower(),
            item.get("language", LANGUAGE).strip().lower(),
            item["translation"].strip().lower(),
        ): item
        for item in existing
    }

    expected = Counter()
    changed = Counter()
    missing = []

    for item in WORDS:
        key = (
            item["word"].strip().lower(),
            LANGUAGE.strip().lower(),
            item["translation"].strip().lower(),
        )
        target_category = item["category"]
        expected[target_category] += 1

        current = by_key.get(key)
        if not current:
            missing.append(item["word"])
            continue

        current_category = (current.get("category") or "saudacoes").strip().lower()
        if current_category == target_category:
            continue

        response = requests.put(
            f"{API_BASE_URL}/vocab-words/{current['id']}",
            json={"category": target_category},
            headers=headers,
        )
        response.raise_for_status()
        changed[target_category] += 1
        print(
            f"Corrigido: {item['word']} | "
            f"{current_category} -> {target_category}"
        )

    print("\nResumo:")
    for category in CATEGORY_ORDER:
        print(
            f"  {category}: {expected[category]} no seed | "
            f"{changed[category]} categorias corrigidas"
        )

    if missing:
        print(f"\n{len(missing)} item(ns) do seed não foram encontrados na base.")
        print("Primeiros:", ", ".join(missing[:20]))
        print("Para criar os que faltam, rode seed_vocab_words.py.")

    print("\nConcluído. O progresso dos alunos não foi alterado.")


if __name__ == "__main__":
    main()
