import os
import sys
import requests

API_BASE_URL = os.environ.get(
    "API_BASE_URL",
    "https://litenglish.up.railway.app"
)

PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

LINGUAS = {"ingles", "frances", "italiano"}


def main():
    if not PROFESSOR_EMAIL or not PROFESSOR_PASSWORD:
        print("ERRO: defina:")
        print("  PROFESSOR_EMAIL")
        print("  PROFESSOR_PASSWORD")
        sys.exit(1)

    print(f"Conectando em {API_BASE_URL}...")

    login = requests.post(
        f"{API_BASE_URL}/auth/login",
        data={
            "username": PROFESSOR_EMAIL,
            "password": PROFESSOR_PASSWORD,
        },
        timeout=30,
    )

    login.raise_for_status()

    token = login.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}"
    }

    print("Buscando todas as palavras...")

    response = requests.get(
        f"{API_BASE_URL}/vocab-words",
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    words = response.json()

    # Somente inglês, francês e italiano.
    words = [
        word for word in words
        if word.get("language", "").strip().lower() in LINGUAS
    ]

    print()
    print("========================================")
    print(" PALAVRAS QUE SERÃO APAGADAS")
    print("========================================")

    for language in sorted(LINGUAS):
        count = sum(
            1 for word in words
            if word.get("language", "").strip().lower() == language
        )
        print(f"{language}: {count}")

    print("----------------------------------------")
    print(f"TOTAL: {len(words)}")
    print("========================================")
    print()

    confirm = input(
        "Digite APAGAR para confirmar a exclusão de TODAS elas: "
    ).strip()

    if confirm != "APAGAR":
        print("Cancelado. Nada foi apagado.")
        return

    deleted = 0
    errors = 0

    print()
    print("Apagando...")

    for word in words:
        word_id = word["id"]

        try:
            resp = requests.delete(
                f"{API_BASE_URL}/vocab-words/{word_id}",
                headers=headers,
                timeout=30,
            )

            if resp.status_code == 204:
                deleted += 1
                print(
                    f"[OK] {word['language']} | "
                    f"{word['word']} | id={word_id}"
                )
            else:
                errors += 1
                print(
                    f"[ERRO] id={word_id} | "
                    f"{resp.status_code} | {resp.text}"
                )

        except Exception as e:
            errors += 1
            print(f"[ERRO] id={word_id} | {e}")

    print()
    print("========================================")
    print(" RESULTADO")
    print("========================================")
    print(f"Apagadas: {deleted}")
    print(f"Erros:    {errors}")
    print("========================================")


if __name__ == "__main__":
    main()