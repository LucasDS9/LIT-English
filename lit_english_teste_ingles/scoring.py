# -*- coding: utf-8 -*-
"""
Sistema de nivelamento - LIT English

Baseado nas 16 questões cadastradas em questions_data.py:
  A1 -> Q1, Q3, Q11, Q13, Q14   (5 questões, peso 1 cada)
  A2 -> Q2, Q4, Q5, Q6, Q8, Q9, Q12  (7 questões, peso 2 cada)
  B1 -> Q7, Q10, Q15   (3 questões, peso 3 cada)
  B2 -> Q16   (1 questão, peso 4)
"""
from questions_data import QUESTIONS_BY_ID, TOTAL_QUESTIONS

WEIGHTS = {"A1": 1, "A2": 2, "B1": 3, "B2": 4}

LEVEL_IDS = {
    "A1": [1, 3, 11, 13, 14],
    "A2": [2, 4, 5, 6, 8, 9, 12],
    "B1": [7, 10, 15],
    "B2": [16],
}

MAX_POINTS = sum(
    WEIGHTS[level] * len(ids) for level, ids in LEVEL_IDS.items()
)  # 5*1 + 7*2 + 3*3 + 1*4 = 32

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
    "EXPERT": {
        "code": "B2",
        "label": "EXPERT",
        "description": (
            "Você demonstrou domínio de estruturas avançadas do inglês, como "
            "reported speech, e está pronto para desafios de nível avançado."
        ),
        "trilha": "EXPERT",
    },
}


def _classify(
    correct_a1: int, total_a1: int,
    correct_a2: int, total_a2: int,
    correct_b1: int, total_b1: int,
    correct_b2: int, total_b2: int,
) -> str:
    """
    Critério em gates (v4):

    - EXPLORER (A2): A1 perfeito (5/5) + pelo menos 4 das 7 de A2.
    - MASTER (B1): A1 perfeito (5/5) + pelo menos 5 das 7 de A2 +
      pelo menos 2 das 3 de B1.
    - EXPERT (B2): tudo do MASTER acima + acerta a única questão de B2.
    - STARTER: quem não bate nem o requisito de EXPLORER.
    """
    passed_a1 = correct_a1 >= total_a1

    passed_a2 = passed_a1 and correct_a2 >= 4
    passed_b1 = passed_a1 and correct_a2 >= 5 and correct_b1 >= 2
    passed_b2 = passed_b1 and correct_b2 >= total_b2

    if passed_b2:
        return "EXPERT"
    if passed_b1:
        return "MASTER"
    if passed_a2:
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
    correct_by_level = {"A1": 0, "A2": 0, "B1": 0, "B2": 0}

    for r in graded_answers:
        level = r["level"]
        if r["is_correct"]:
            points += WEIGHTS[level]
            correct_by_level[level] += 1

    pct_geral = round((correct_count / TOTAL_QUESTIONS) * 100)

    total_a1 = len(LEVEL_IDS["A1"])
    total_a2 = len(LEVEL_IDS["A2"])
    total_b1 = len(LEVEL_IDS["B1"])
    total_b2 = len(LEVEL_IDS["B2"])

    pct_a1 = round((correct_by_level["A1"] / total_a1) * 100)
    pct_a2 = round((correct_by_level["A2"] / total_a2) * 100)
    pct_b1 = round((correct_by_level["B1"] / total_b1) * 100)
    pct_b2 = round((correct_by_level["B2"] / total_b2) * 100)

    nivel = _classify(
        correct_by_level["A1"], total_a1,
        correct_by_level["A2"], total_a2,
        correct_by_level["B1"], total_b1,
        correct_by_level["B2"], total_b2,
    )
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
        "percent_b2": pct_b2,
        "correct_a1": correct_by_level["A1"],
        "correct_a2": correct_by_level["A2"],
        "correct_b1": correct_by_level["B1"],
        "correct_b2": correct_by_level["B2"],
        "total_a1": total_a1,
        "total_a2": total_a2,
        "total_b1": total_b1,
        "total_b2": total_b2,
        "nivel_estimado": nivel,          # STARTER | EXPLORER | MASTER | EXPERT
        "nivel_codigo": info["code"],     # A1 | A2 | B1 | B2
        "nivel_descricao": info["description"],
        "trilha_recomendada": info["trilha"],
    }
