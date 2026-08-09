"""
Script de seed: cria OU ATUALIZA as palavras da tela "Aprender" via API
(upsert). Como o campo `student_ids` é OPCIONAL (ver
VocabWordCreate/create_vocab_word), não enviamos ele aqui de propósito — a
API atribui a palavra automaticamente a todos os alunos aprovados no
momento **que tenham a mesma língua-alvo** (campo `language`, abaixo —
"ingles" aqui), e o backend garante que qualquer aluno aprovado depois (em
admin.approve_student) dessa mesma língua também receba as mesmas palavras.
Ou seja: a partir daqui, as palavras cadastradas aqui ficam nativas para
todo aluno de inglês (curso normal) que cria conta e é aprovado, sem
precisar selecionar aluno por aluno — e nunca vão parar num aluno de Acesso
Especial (ex.: italiano).

COMPORTAMENTO DE UPSERT (criar, atualizar ou deixar como está):
Antes de enviar cada item de WORDS, o script busca em GET /vocab-words se
já existe uma palavra com o mesmo texto (`word`, sem diferenciar
maiúscula/minúscula) e a mesma LANGUAGE. A partir daí:
- Não existe ainda            -> cria via POST /vocab-words ("Criado").
- Existe e está diferente     -> atualiza via PUT /vocab-words/{id}
                                  ("Atualizado").
- Existe e já está idêntica   -> não faz nenhuma chamada de escrita
                                  ("Inalterado").
Ou seja: o fluxo do dia a dia é editar a lista WORDS abaixo (mudar uma
tradução, corrigir uma dica, adicionar uma palavra nova no final) e rodar
o script de novo — nunca duplica nada, e só grava no banco o que de fato
mudou. No final, o script imprime um resumo com a contagem de cada caso.

Pra um lote de outra língua (ex.: italiano), copie este script e troque
LANGUAGE abaixo — o resto do fluxo (login, upsert em /vocab-words) é igual.

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
na lista WORDS abaixo, seguindo o mesmo formato.
"""
import os
import sys

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://litenglish.up.railway.app")
PROFESSOR_EMAIL = os.environ.get("PROFESSOR_EMAIL")
PROFESSOR_PASSWORD = os.environ.get("PROFESSOR_PASSWORD")

# Língua-alvo deste lote de palavras. Alunos do curso normal são sempre
# "ingles"; alunos de Acesso Especial usam o target_language do cadastro
# (ex.: "italiano").
LANGUAGE = "ingles"

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
        "translation": "Oi",
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


def _norm(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _needs_update(existing: dict, item: dict, language: str) -> bool:
    """
    Compara o que já está cadastrado com o que o item de WORDS quer enviar.
    Só chamamos o PUT se algo realmente for diferente — assim uma palavra
    que já está em dia não sofre uma escrita desnecessária no banco.
    """
    if existing["word"].strip() != item["word"].strip():
        return True
    if existing["part_of_speech"].strip() != item["part_of_speech"].strip():
        return True
    if existing["translation"].strip() != item["translation"].strip():
        return True
    if _norm(existing.get("example_sentence")) != _norm(item.get("example_sentence")):
        return True
    if _norm(existing.get("tip")) != _norm(item.get("tip")):
        return True
    existing_distractors = sorted(d.strip().lower() for d in existing["distractors"])
    item_distractors = sorted(d.strip().lower() for d in item["distractors"])
    if existing_distractors != item_distractors:
        return True
    if existing["language"].strip().lower() != language.strip().lower():
        return True
    return False


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

    summary = {"Criado": 0, "Atualizado": 0, "Inalterado": 0}

    for item in WORDS:
        key = (item["word"].strip().lower(), LANGUAGE.strip().lower())
        existing = existing_words.get(key)

        # Sem `student_ids`: na CRIAÇÃO, a API atribui automaticamente a
        # todos os alunos aprovados agora (e aos aprovados depois) que
        # tenham a mesma língua-alvo (LANGUAGE, acima). Na ATUALIZAÇÃO, não
        # reenviamos student_ids de propósito, pra não alterar quem já está
        # atribuído à palavra.
        payload = {**item, "language": LANGUAGE}

        if existing and not _needs_update(existing, item, LANGUAGE):
            # Já está tudo igual: não chama a API, só reporta.
            n_students = len(existing.get("students", []))
            print(f"Inalterado: '{existing['word']}' (id={existing['id']}) -> {existing['translation']} "
                  f"[{n_students} aluno(s) atribuído(s)]")
            summary["Inalterado"] += 1
            continue

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
        summary[action] += 1

    print(
        f"Concluído. Criado: {summary['Criado']} | "
        f"Atualizado: {summary['Atualizado']} | "
        f"Inalterado: {summary['Inalterado']}"
    )


if __name__ == "__main__":
    main()
