"""
Script de seed: cria OU ATUALIZA (upsert) as palavras da tela "Aprender"
(saudações) em ITALIANO, via API. É a versão em italiano de
`seed_vocab_words.py` (que cadastra as mesmas 5 saudações em inglês) —
mesmo formato, mesmo fluxo, só troca a LANGUAGE e o conteúdo das palavras.

Como o campo `student_ids` é OPCIONAL (ver VocabWordCreate/create_vocab_word),
não enviamos ele aqui de propósito — a API atribui a palavra automaticamente
a todos os alunos aprovados no momento **que tenham a mesma língua-alvo**
(campo `language`, abaixo — "italiano" aqui, ou seja: alunos de Acesso
Especial com target_language == "italiano"), e o backend garante que
qualquer aluno aprovado depois (em admin.approve_student) dessa mesma
língua também receba as mesmas palavras.

COMPORTAMENTO DE UPSERT (criar ou atualizar, sem duplicar):
Antes de enviar cada item de WORDS, o script busca em GET /vocab-words se
já existe uma palavra com o mesmo texto (`word`, sem diferenciar
maiúscula/minúscula) e a mesma LANGUAGE. Se existir, atualiza essa palavra
via PUT /vocab-words/{id}. Se não existir, cria via POST /vocab-words. Ou
seja: pra editar algo, é só mudar a lista WORDS abaixo e rodar o script de
novo — nunca duplica nada.

Uso:
    cd lit_english_backend
    pip install requests
    API_BASE_URL="https://litenglish.up.railway.app" \
    PROFESSOR_EMAIL="seu-email@exemplo.com" \
    PROFESSOR_PASSWORD="sua-senha" \
    python scripts/seed_vocab_words_italiano.py

Este arquivo contém, por enquanto, só as 5 primeiras palavras (saudações)
como TESTE — o mesmo recorte usado no lote de inglês. As demais (o restante
das saudações + a tabela de expressões comuns) podem ser acrescentadas
depois na lista WORDS abaixo, seguindo o mesmo formato.
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# Língua-alvo deste lote de palavras. Alunos de Acesso Especial usam o
# target_language escolhido no cadastro — hoje o único valor aceito além de
# "ingles" é "italiano".
LANGUAGE = "italiano"

# ---------------------------------------------------------------------------
# TESTE: as 5 primeiras saudações, em italiano — mesma estrutura do lote de
# inglês (Hi/Hello/Good morning/Good afternoon/Good evening), usando `tip`
# no lugar de `example_sentence` (saudações não têm frase de exemplo).
#
# "Ciao" (informal) equivale a "Hi"; "Salve" (neutro/levemente mais formal)
# equivale a "Hello", já que o italiano não tem duas palavras tão separadas
# quanto o inglês para esse par.
# ---------------------------------------------------------------------------
WORDS = [
    {
        "word": "Ciao",
        "part_of_speech": "saudação",
        "tip": "Saudação informal e muito comum.",
        "translation": "Oi",
        "distractors": ["Até mais", "Boa noite", "Adeus"],
    },
    {
        "word": "Salve",
        "part_of_speech": "saudação",
        "tip": "Saudação neutra, um pouco mais formal que 'Ciao'.",
        "translation": "Olá",
        "distractors": ["Tchau", "Até amanhã", "Se cuida"],
    },
    {
        "word": "Buongiorno",
        "part_of_speech": "saudação",
        "tip": "Para cumprimentar alguém pela manhã.",
        "translation": "Bom dia",
        "distractors": ["Boa tarde", "Boa noite", "Até mais"],
    },
    {
        "word": "Buon pomeriggio",
        "part_of_speech": "saudação",
        "tip": "Para cumprimentar alguém à tarde.",
        "translation": "Boa tarde",
        "distractors": ["Boa noite", "Até mais", "Bom dia"],
    },
    {
        "word": "Buonasera",
        "part_of_speech": "saudação",
        "tip": "Para cumprimentar alguém à noite.",
        "translation": "Boa noite",
        "distractors": ["Boa tarde", "Bom dia", "Até mais"],
    },
]


def _fetch_existing_words(api_base_url: str, headers: dict) -> dict:
    """
    Busca todas as palavras já cadastradas (GET /vocab-words, visão do
    professor) e devolve um dicionário {(word_lower, language): word_dict},
    pra decidir rapidamente se cada item de WORDS já existe ou não.
    """
    resp = requests.get(f"{api_base_url}/vocab-words", headers=headers)
    resp.raise_for_status()
    existing = {}
    for w in resp.json():
        key = (w["word"].strip().lower(), w["language"].strip().lower())
        existing[key] = w
    return existing


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

    print("Verificando palavras já cadastradas...")
    existing_words = _fetch_existing_words(API_BASE_URL, headers)

    for item in WORDS:
        key = (item["word"].strip().lower(), LANGUAGE.strip().lower())
        existing = existing_words.get(key)

        # Sem `student_ids`: na CRIAÇÃO, a API atribui automaticamente a
        # todos os alunos aprovados agora (e aos aprovados depois) que
        # tenham a mesma língua-alvo (LANGUAGE, acima — "italiano"). Na
        # ATUALIZAÇÃO, não reenviamos student_ids de propósito, pra não
        # alterar quem já está atribuído à palavra.
        payload = {**item, "language": LANGUAGE}

        if existing:
            word_id = existing["id"]
            resp = requests.put(f"{API_BASE_URL}/vocab-words/{word_id}", json=payload, headers=headers)
            action = "Atualizado"
        else:
            resp = requests.post(f"{API_BASE_URL}/vocab-words", json=payload, headers=headers)
            action = "Criado"

        if resp.status_code >= 400:
            verbo = "atualizar" if existing else "criar"
            print(f"Falha ao {verbo} '{item['word']}': {resp.status_code} {resp.text}")
            continue

        result = resp.json()
        n_students = len(result.get("students", []))
        print(f"{action}: '{result['word']}' (id={result['id']}) -> {result['translation']} "
              f"[{n_students} aluno(s) atribuído(s)]")

    print("Concluído.")


if __name__ == "__main__":
    main()
