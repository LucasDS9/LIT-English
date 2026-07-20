# -*- coding: utf-8 -*-
"""
Armazenamento simples dos resultados dos testes em um arquivo JSON local.

Para produção, isso pode ser trocado por um banco de verdade (SQLite/Postgres)
sem alterar a interface (save_result / list_results) usada pelo app.py.
"""
import json
import os
import threading
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

_lock = threading.Lock()


def _ensure_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def save_result(nome: str, whatsapp: str, score: dict) -> dict:
    """
    Salva um resultado de teste e retorna o registro salvo (com id e data).
    """
    _ensure_storage()
    with _lock:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)

        record = {
            "id": len(results) + 1,
            "nome": nome.strip() if nome else "Aluno",
            "whatsapp": (whatsapp or "").strip(),
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "acertos": score["correct_count"],
            "erros": score["wrong_count"],
            "total_questoes": score["total_questions"],
            "porcentagem": score["percent_geral"],
            "pontos": score["points"],
            "pontuacao_maxima": score["max_points"],
            "desempenho_a1": score["percent_a1"],
            "desempenho_a2": score["percent_a2"],
            "desempenho_b1": score["percent_b1"],
            "nivel_estimado": score["nivel_estimado"],
            "trilha_recomendada": score["trilha_recomendada"],
        }

        results.append(record)

        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        return record


def update_whatsapp(record_id: int, whatsapp: str, interesses: dict = None) -> dict | None:
    """
    Atualiza o WhatsApp de um registro já salvo (usado quando o aluno
    deixa o número na tela de resultado, depois do teste já corrigido).
    Opcionalmente recebe os interesses marcados (aula experimental,
    análise/plano de estudos). Retorna o registro atualizado, ou None
    se o id não existir.
    """
    _ensure_storage()
    with _lock:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)

        updated = None
        for record in results:
            if record.get("id") == record_id:
                record["whatsapp"] = (whatsapp or "").strip()
                if interesses is not None:
                    record["quer_aula_experimental"] = bool(interesses.get("aula_experimental"))
                    record["quer_analise_plano"] = bool(interesses.get("analise_plano"))
                updated = record
                break

        if updated is not None:
            with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        return updated


def list_results(days: int = None) -> list:
    """
    Retorna todos os resultados salvos, mais recentes primeiro.
    (o filtro por período de dias pode ser feito no front-end com a data
    já formatada, ou aqui futuramente parseando 'data')
    """
    _ensure_storage()
    with _lock:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    return list(reversed(results))
