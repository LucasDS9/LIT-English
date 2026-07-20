# -*- coding: utf-8 -*-
"""
Sistema de nivelamento - LIT English

Baseado nas 15 questões cadastradas em questions_data.py:
  A1 -> Q1, Q3, Q11, Q13, Q14   (5 questões, peso 1 cada)
  A2 -> Q2, Q4, Q5, Q6, Q8, Q9, Q12  (7 questões, peso 2 cada)
  B1 -> Q7, Q10, Q15   (3 questões, peso 3 cada)
"""
from questions_data import QUESTIONS_BY_ID, TOTAL_QUESTIONS

WEIGHTS = {"A1": 1, "A2": 2, "B1": 3}

LEVEL_IDS = {
    "A1": [1, 3, 11, 13, 14],
    "A2": [2, 4, 5, 6, 8, 9, 12],
    "B1": [7, 10, 15],
}

MAX_POINTS = sum(
    WEIGHTS[level] * len(ids) for level, ids in LEVEL_IDS.items()
)  # 3*1 + 7*2 + 2*3 = 23

LEVEL_INFO = {
    "STARTER": {
        "code": "A1",
        "label": "STARTER",
        "description": (
            "Você já domina o básico do inglês e está pronto para expandir "
            "seu vocabulário e gramática com mais prática."
        ),
        "trilha": "STARTER",
    },
    "EXPLORER": {
        "code": "A2",
        "label": "EXPLORER",
        "description": (
            "Você demonstrou boa compreensão do inglês em situações do dia a "
            "dia e já começa a usar estruturas mais complexas com confiança."
        ),
        "trilha": "EXPLORER",
    },
    "MASTER": {
        "code": "B1",
        "label": "MASTER",
        "description": (
            "Você demonstrou domínio das estruturas gramaticais básicas e "
            "intermediárias e já compreende construções mais avançadas."
        ),
        "trilha": "MASTER",
    },
}


def _classify(pct_a1: float, pct_a2: float, pct_b1: float, pct_geral: float) -> str:
    """
    Critério rebalanceado (v2):

    O desempenho GERAL passa a ser o principal fator, com o desempenho por
    nível funcionando como um "gate" mais leve (garante que o aluno tem
    familiaridade mínima com aquele patamar, sem exigir domínio quase total
    dele antes de subir de nível).

    - MASTER (B1): bom desempenho geral (>=75%) e já mostra alguma
      familiaridade com A1 (>=60%) e com B1 (pelo menos 1 das 3 questões).
    - EXPLORER (A2): já saiu do "só sei o básico" — desempenho geral
      razoável (>=45%) com o mínimo de base em A1 (>=40%).
    - STARTER (A1): reservado para quem ainda está apoiado só no básico
      (desempenho geral baixo ou pouca base mesmo em A1).
    """
    if pct_geral >= 75 and pct_a1 >= 60 and pct_b1 >= 33:
        return "MASTER"
    if pct_geral >= 45 and pct_a1 >= 40:
        return "EXPLORER"
    return "STARTER"


def compute_score(graded_answers: list) -> dict:
    """
    graded_answers: saída de grading.grade_all_answers()

    Retorna um dicionário com todos os dados do resultado final,
    prontos para exibir ao aluno e para salvar no painel do professor.
    """
    correct_count = sum(1 for r in graded_answers if r["is_correct"])
    wrong_count = len(graded_answers) - correct_count

    points = 0
    correct_by_level = {"A1": 0, "A2": 0, "B1": 0}

    for r in graded_answers:
        level = r["level"]
        if r["is_correct"]:
            points += WEIGHTS[level]
            correct_by_level[level] += 1

    pct_geral = round((correct_count / TOTAL_QUESTIONS) * 100)

    pct_a1 = round((correct_by_level["A1"] / len(LEVEL_IDS["A1"])) * 100)
    pct_a2 = round((correct_by_level["A2"] / len(LEVEL_IDS["A2"])) * 100)
    pct_b1 = round((correct_by_level["B1"] / len(LEVEL_IDS["B1"])) * 100)

    nivel = _classify(pct_a1, pct_a2, pct_b1, pct_geral)
    info = LEVEL_INFO[nivel]

    return {
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "total_questions": TOTAL_QUESTIONS,
        "percent_geral": pct_geral,
        "points": points,
        "max_points": MAX_POINTS,
        "percent_a1": pct_a1,
        "percent_a2": pct_a2,
        "percent_b1": pct_b1,
        "correct_a1": correct_by_level["A1"],
        "correct_a2": correct_by_level["A2"],
        "correct_b1": correct_by_level["B1"],
        "total_a1": len(LEVEL_IDS["A1"]),
        "total_a2": len(LEVEL_IDS["A2"]),
        "total_b1": len(LEVEL_IDS["B1"]),
        "nivel_estimado": nivel,          # STARTER | EXPLORER | MASTER
        "nivel_codigo": info["code"],     # A1 | A2 | B1
        "nivel_descricao": info["description"],
        "trilha_recomendada": info["trilha"],
    }
