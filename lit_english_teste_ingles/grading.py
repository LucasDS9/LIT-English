# -*- coding: utf-8 -*-
"""
Corrige as respostas do aluno questão a questão.
"""
import re
import unicodedata

from questions_data import QUESTIONS_BY_ID


def _normalize_text(text: str) -> str:
    """minúsculas, sem acento, sem pontuação, espaços colapsados"""
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _translation_is_correct(question: dict, student_answer: str) -> bool:
    normalized_answer = _normalize_text(student_answer)
    if not normalized_answer:
        return False

    for accepted in question["accepted_answers"]:
        if normalized_answer == _normalize_text(accepted):
            return True
    return False


def grade_single_answer(question_id: int, student_answer):
    """
    Corrige uma única resposta.
    Retorna um dict com o resultado detalhado daquela questão.

    Regras de exibição (sempre respeitadas aqui, para nunca contradizer o
    resultado real do aluno):
    - Se ACERTOU: "summary" = "Correto!" e "explanation" traz o motivo,
      sem nenhuma referência à resposta errada.
    - Se ERROU: "summary" = "O correto seria: <resposta certa>. Você
      escolheu/respondeu: <resposta do aluno>." e "explanation" traz o
      motivo de a alternativa escolhida estar errada (nunca a palavra
      "Correto!").
    """
    question = QUESTIONS_BY_ID.get(question_id)
    if question is None:
        raise ValueError(f"Questão {question_id} não existe.")

    q_type = question["type"]
    result = {
        "id": question["id"],
        "number": question["number"],
        "type": q_type,
        "level": question["level"],
        "subject": question["subject"],
        "question_en": question.get("question_en"),
        "question_pt": question.get("question_pt"),
        "direction": question.get("direction"),
        "student_answer": student_answer,
        "is_correct": False,
        "summary": "",
        "explanation": "",
        "reference_answer": None,
        "correct_key": None,
        "chosen_text": None,
        "correct_text": None,
    }

    if q_type in ("fill", "listening"):
        student_key = (student_answer or "").strip().lower()
        correct_key = question["correct_key"]
        result["correct_key"] = correct_key

        chosen_option = next(
            (o for o in question["options"] if o["key"] == student_key), None
        )
        correct_option = next(
            o for o in question["options"] if o["key"] == correct_key
        )
        result["is_correct"] = bool(chosen_option) and student_key == correct_key
        result["chosen_text"] = chosen_option["text"] if chosen_option else None
        result["correct_text"] = correct_option["text"]

        if result["is_correct"]:
            # Acertou: só mostramos "Correto!" + a explicação da própria
            # alternativa certa. Nunca misturamos com a fala de erro.
            result["summary"] = "Correto!"
            result["explanation"] = correct_option["feedback"]
        else:
            chosen_label = chosen_option["text"] if chosen_option else "nenhuma resposta"
            if q_type == "fill":
                result["summary"] = (
                    f'O correto seria "{correct_option["text"]}". '
                    f'Você escolheu "{chosen_label}".'
                )
                result["explanation"] = (
                    chosen_option["feedback"] if chosen_option else "Resposta não reconhecida."
                )
            else:
                # listening: o texto de cada opção já é uma explicação
                # completa e específica, então usamos direto, sem "Correto!".
                result["summary"] = ""
                result["explanation"] = (
                    chosen_option["feedback"] if chosen_option else "Resposta não reconhecida."
                )

    elif q_type == "translation":
        result["is_correct"] = _translation_is_correct(question, student_answer)
        result["reference_answer"] = question["reference_answer"]
        grammar_note = question.get("grammar_note", "")

        if result["is_correct"]:
            result["summary"] = "Correto!"
            result["explanation"] = grammar_note
        else:
            student_label = student_answer.strip() if student_answer else "(em branco)"
            result["summary"] = (
                f'O correto seria: "{question["reference_answer"]}". '
                f'Você respondeu: "{student_label}".'
            )
            result["explanation"] = grammar_note

    else:
        raise ValueError(f"Tipo de questão desconhecido: {q_type}")

    return result


def grade_all_answers(answers: dict):
    """
    answers: { "1": "c", "2": "c", ..., "6": "eu estava estudando", ... }
    (chaves como string ou int, ambos funcionam)

    Retorna a lista de resultados detalhados, na ordem das questões.
    """
    from questions_data import QUESTIONS

    graded = []
    for question in QUESTIONS:
        qid = question["id"]
        student_answer = answers.get(str(qid), answers.get(qid, ""))
        graded.append(grade_single_answer(qid, student_answer))
    return graded
