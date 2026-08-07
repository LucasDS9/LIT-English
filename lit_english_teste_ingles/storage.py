# -*- coding: utf-8 -*-
"""
Armazenamento dos resultados do teste — agora gravados direto no backend
principal (lit_english_backend), via a API /level-test/*, em vez de um
arquivo JSON local.

Isso é o que permite que os leads (quem terminou o teste e deixou o
WhatsApp) apareçam no painel do professor do site principal, que já usa
esse mesmo banco de dados.
"""
import os

import requests

# Ajuste esta URL para onde o backend principal (lit_english_backend)
# estiver rodando.
BACKEND_URL = os.environ.get("BACKEND_URL", "https://litenglish.up.railway.app")

_TIMEOUT = 8  # segundos


def _trim_question_detail(r: dict) -> dict:
    """Mantém só os campos que interessam ao painel do professor (o "Ver
    mais" de cada lead) — descarta summary/explanation/correct_key, que são
    só para a tela do aluno."""
    return {
        "id": r["id"],
        "number": r.get("number"),
        "type": r.get("type"),
        "level": r.get("level"),
        "subject": r.get("subject"),
        "question_en": r.get("question_en"),
        "question_pt": r.get("question_pt"),
        "is_correct": r.get("is_correct", False),
        "student_answer": r.get("student_answer"),
        "chosen_text": r.get("chosen_text"),
        "correct_text": r.get("correct_text"),
        "reference_answer": r.get("reference_answer"),
    }


def save_result(nome: str, whatsapp: str, score: dict, graded_answers: list = None) -> dict:
    """
    Salva um resultado de teste no backend principal e retorna o registro
    salvo (com id). Se o backend estiver fora do ar, não derruba o teste do
    aluno — apenas não fica com WhatsApp/histórico registrado dessa vez.

    graded_answers: saída de grading.grade_all_answers() — enviada junto
    para que o professor veja, questão a questão, o que o aluno acertou/
    errou e o que escolheu/digitou (botão "Ver mais" nos leads do teste).
    """
    payload = {
        "nome": (nome or "Aluno").strip(),
        "whatsapp": (whatsapp or "").strip(),
        "acertos": score["correct_count"],
        "erros": score["wrong_count"],
        "total_questoes": score["total_questions"],
        "porcentagem": score["percent_geral"],
        "pontos": score["points"],
        "pontuacao_maxima": score["max_points"],
        "desempenho_a1": score["percent_a1"],
        "desempenho_a2": score["percent_a2"],
        "desempenho_b1": score["percent_b1"],
        "desempenho_b2": score["percent_b2"],
        "nivel_estimado": score["nivel_estimado"],
        "trilha_recomendada": score["trilha_recomendada"],
        "quer_aula_experimental": False,
        "quer_analise_plano": False,
        "respostas_detalhadas": [_trim_question_detail(r) for r in (graded_answers or [])],
    }
    try:
        resp = requests.post(f"{BACKEND_URL}/level-test/submit", json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        # Backend indisponível: devolve um registro "local" sem id real,
        # pra tela de resultado do aluno continuar funcionando normalmente.
        return {**payload, "id": None}


def update_whatsapp(record_id, whatsapp: str, interesses: dict = None) -> dict | None:
    """
    Atualiza o WhatsApp (e os interesses marcados) de um registro já salvo
    no backend principal. Retorna o registro atualizado, ou None se não foi
    possível (backend fora do ar ou id inválido).
    """
    if not record_id:
        return None

    interesses = interesses or {}
    payload = {
        "whatsapp": (whatsapp or "").strip(),
        "quer_aula_experimental": bool(interesses.get("aula_experimental")),
        "quer_analise_plano": bool(interesses.get("analise_plano")),
    }
    try:
        resp = requests.patch(
            f"{BACKEND_URL}/level-test/{record_id}/whatsapp", json=payload, timeout=_TIMEOUT
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None
