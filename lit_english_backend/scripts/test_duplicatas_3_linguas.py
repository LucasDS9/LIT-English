#!/usr/bin/env python3
"""
Verificador de duplicatas de vocabulário — Inglês, Italiano e Francês.

Uso:
    python test_duplicatas_3_linguas.py

O script procura automaticamente os seeds do projeto e informa:
1. Total de entradas por idioma
2. Palavras únicas
3. Duplicatas exatas (palavra + tradução)
4. Palavras repetidas com traduções diferentes
5. Resumo final comparando as 3 línguas

Ele não altera nenhum arquivo nem o banco de dados.
"""

from pathlib import Path
import ast
import re
import sys
from collections import Counter, defaultdict

LANGUAGES = {
    "inglês": ["english", "ingles", "en"],
    "italiano": ["italian", "italiano", "it"],
    "francês": ["french", "frances", "francês", "fr"],
}


def normalize(value):
    """Normalização usada apenas para detectar duplicatas."""
    if value is None:
        return ""
    value = str(value).strip().casefold()
    value = re.sub(r"\s+", " ", value)
    return value


def find_project_root():
    here = Path(__file__).resolve().parent

    # scripts/ -> backend/ -> projeto
    candidates = [
        here.parent.parent,
        here.parent,
        here,
        Path.cwd(),
    ]

    for candidate in candidates:
        if candidate.exists():
            # Preferir diretórios que tenham arquivos Python de seed.
            py_files = list(candidate.rglob("*.py"))
            if py_files:
                return candidate

    return Path.cwd()


def classify_file(path):
    name = path.name.casefold()
    for language, terms in LANGUAGES.items():
        if any(term in name for term in terms):
            return language
    return None


def extract_vocab_from_python(path):
    """
    Tenta extrair listas/dicionários de vocabulário de arquivos Python
    sem executar o seed.

    Aceita estruturas comuns:
      ("word", "translation")
      {"word": "...", "translation": "..."}
      {"en": "...", "pt": "..."}
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except Exception:
        return []

    pairs = []

    def literal(node):
        try:
            return ast.literal_eval(node)
        except Exception:
            return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            value = literal(node)
            if not isinstance(value, (list, tuple, set)):
                continue

            for item in value:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    a, b = item[0], item[1]
                    if isinstance(a, str) and isinstance(b, str):
                        pairs.append((a, b, path))

                elif isinstance(item, dict):
                    word = None
                    translation = None

                    for key in ("word", "term", "source", "text", "english",
                                "italian", "italiano", "french", "francais",
                                "français", "en", "it", "fr"):
                        if key in item and isinstance(item[key], str):
                            word = item[key]
                            break

                    for key in ("translation", "translated", "meaning", "pt",
                                "portuguese", "portugues", "português"):
                        if key in item and isinstance(item[key], str):
                            translation = item[key]
                            break

                    if word and translation:
                        pairs.append((word, translation, path))

        elif isinstance(node, ast.Dict):
            value = literal(node)
            if isinstance(value, dict):
                # Caso o próprio dicionário seja uma entrada de vocabulário.
                word = None
                translation = None

                for key in ("word", "term", "source", "text"):
                    if isinstance(value.get(key), str):
                        word = value[key]
                        break

                for key in ("translation", "translated", "meaning", "pt"):
                    if isinstance(value.get(key), str):
                        translation = value[key]
                        break

                if word and translation:
                    pairs.append((word, translation, path))

    # Remove cópias causadas por nós AST aninhados.
    unique = {}
    for word, translation, path in pairs:
        key = (normalize(word), normalize(translation), str(path))
        unique[key] = (word, translation, path)

    return list(unique.values())


def main():
    root = find_project_root()
    print("=" * 72)
    print(" TESTE DE DUPLICATAS — INGLÊS / ITALIANO / FRANCÊS")
    print("=" * 72)
    print(f"Projeto: {root}")
    print()

    files_by_language = defaultdict(list)

    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue

        language = classify_file(path)
        if language:
            files_by_language[language].append(path)

    all_found = False
    grand_total = 0

    for language in ("inglês", "italiano", "francês"):
        print("-" * 72)
        print(language.upper())

        files = files_by_language.get(language, [])
        if not files:
            print("⚠ Nenhum seed/arquivo encontrado automaticamente.")
            print()
            continue

        entries = []
        for path in files:
            entries.extend(extract_vocab_from_python(path))

        # Remove entradas idênticas encontradas em múltiplos arquivos.
        seen_source = {}
        for word, translation, path in entries:
            key = (normalize(word), normalize(translation))
            seen_source.setdefault(key, []).append(path)

        unique_keys = set(seen_source)
        total = len(entries)
        unique_words = len(set(normalize(w) for w, _, _ in entries))

        exact_duplicates = {
            key: paths
            for key, paths in seen_source.items()
            if len(paths) > 1
        }

        by_word = defaultdict(list)
        for word, translation, path in entries:
            by_word[normalize(word)].append((word, translation, path))

        repeated_words = {
            word: values
            for word, values in by_word.items()
            if len(values) > 1
        }

        same_word_different_translation = {
            word: values
            for word, values in repeated_words.items()
            if len(set(normalize(v[1]) for v in values)) > 1
        }

        grand_total += total

        print(f"Arquivos encontrados: {len(files)}")
        print(f"Entradas lidas:      {total}")
        print(f"Palavras únicas:     {unique_words}")
        print(f"Duplicatas exatas:   {len(exact_duplicates)}")
        print(f"Palavras repetidas:  {len(repeated_words)}")
        print(
            "Repetidas com traduções diferentes: "
            f"{len(same_word_different_translation)}"
        )

        if exact_duplicates:
            all_found = True
            print("\n[!] DUPLICATAS EXATAS")
            for (word, translation), paths in sorted(exact_duplicates.items()):
                print(f'  "{word}" → "{translation}"')
                for p in paths:
                    print(f"      {p}")

        if same_word_different_translation:
            all_found = True
            print("\n[!] MESMA PALAVRA COM TRADUÇÕES DIFERENTES")
            for word, values in sorted(same_word_different_translation.items()):
                print(f'  "{word}"')
                shown = set()
                for original, translation, path in values:
                    item = (translation, str(path))
                    if item in shown:
                        continue
                    shown.add(item)
                    print(f'      → "{translation}"  [{path.name}]')

        print()

    print("=" * 72)
    print("RESUMO")
    print("=" * 72)

    for language in ("inglês", "italiano", "francês"):
        files = files_by_language.get(language, [])
        entries = []
        for path in files:
            entries.extend(extract_vocab_from_python(path))

        print(f"{language.title():10} | {len(entries):4} entradas | "
              f"{len(set(normalize(w) for w, _, _ in entries)):4} palavras únicas")

    print()
    if all_found:
        print("⚠ Foram encontradas possíveis duplicatas. Veja os detalhes acima.")
    else:
        print("✓ Nenhuma duplicata detectada nos seeds encontrados.")

    print()
    print("IMPORTANTE: o teste NÃO modifica arquivos nem o banco de dados.")
    print("Se os números ainda não baterem, compare também o conteúdo do banco")
    print("com os seeds, pois este teste analisa os arquivos Python encontrados.")


if __name__ == "__main__":
    main()
