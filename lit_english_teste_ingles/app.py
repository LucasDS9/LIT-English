# -*- coding: utf-8 -*-
"""
LIT English - Teste de Nivelamento (Flask)

Serviço independente do backend principal (FastAPI, lit_english_backend).
Roda em uma porta própria (5050) e é aberto a partir do botão "Teste de
Inglês" na landing page (lit_english_frontend/index.html).

Rotas de página:
  GET  /                     -> tela inicial (pede o nome do aluno)
  GET  /quiz                 -> tela do teste (uma questão por vez)

Rotas de API:
  GET  /api/questions        -> lista as questões (sem gabarito) para o aluno responder
  POST /api/start            -> recebe o nome digitado e libera o início do teste
  POST /api/check            -> corrige uma questão por vez (feedback imediato)
  POST /api/submit           -> corrige todas as respostas, calcula nível e salva o resultado
  POST /api/whatsapp         -> salva o WhatsApp (e interesses) depois do resultado

O painel do professor (com os leads que deixaram WhatsApp) fica no site
principal (lit_english_frontend/professor.html, atrás de login) — os
resultados são gravados direto no backend principal via storage.py, não
existe mais um painel separado aqui.

Como rodar (junto com o resto do projeto):
  cd lit_english_teste_ingles
  python3 -m venv venv && source venv/bin/activate
  pip install -r requirements.txt
  python3 app.py
  -> sobe em http://127.0.0.1:5050
"""
from flask import Flask, jsonify, render_template, request

from questions_data import QUESTIONS
from grading import grade_all_answers, grade_single_answer
from scoring import compute_score
from storage import save_result, update_whatsapp

app = Flask(__name__)


# ==========================================================================
# Páginas (front-end)
# ==========================================================================
@app.get("/")
def home():
    """Tela inicial: pede o nome do aluno."""
    return render_template("index.html")


@app.get("/quiz")
def quiz_page():
    """Tela do teste: Fill in the Blank / Tradução / Listening, uma questão por vez."""
    return render_template("quiz.html")


def _public_question(question: dict) -> dict:
    """Remove gabarito/feedback antes de mandar a questão para o aluno."""
    public = {
        "id": question["id"],
        "number": question["number"],
        "type": question["type"],
        "subject": question["subject"],
        "question_en": question.get("question_en"),
        "question_pt": question.get("question_pt"),
        "direction": question.get("direction"),
        "translation_pt": question.get("translation_pt"),
    }
    if question["type"] in ("fill", "listening"):
        public["options"] = [
            {"key": o["key"], "text": o["text"]} for o in question["options"]
        ]
    return public


@app.get("/api/questions")
def get_questions():
    return jsonify({
        "total": len(QUESTIONS),
        "questions": [_public_question(q) for q in QUESTIONS],
    })


@app.post("/api/start")
def start_test():
    """
    Body JSON esperado: { "nome": "Lucas" }

    Libera o início do teste normal com o nome informado.
    """
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()

    if not nome:
        return jsonify({"error": "Informe seu nome para continuar."}), 400

    return jsonify({"redirect": "quiz", "nome": nome})


@app.post("/api/check")
def check_answer():
    """
    Corrige UMA questão por vez, para o front-end mostrar o feedback
    (Resposta correta/incorreta) na hora, antes de ir para a próxima.

    Body JSON esperado: { "id": 2, "answer": "c" }
    (para translation, "answer" e o texto digitado pelo aluno)

    Isso NAO salva nada no painel do professor - apenas corrige.
    O envio final (com todas as respostas) continua em /api/submit.
    """
    data = request.get_json(silent=True) or {}
    try:
        question_id = int(data.get("id"))
    except (TypeError, ValueError):
        return jsonify({"error": "id da questao invalido."}), 400

    answer = data.get("answer", "")

    try:
        result = grade_single_answer(question_id, answer)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(result)


@app.post("/api/submit")
def submit_test():
    """
    Body JSON esperado:
    {
      "nome": "Andrielle",
      "whatsapp": "(81) 98765-4321",   # opcional
      "answers": {
         "1": "c", "2": "c", "3": "b", "4": "c", "5": "a",
         "6": "Eu estava estudando",
         "7": "Eu não gostaria disso",
         "8": "Meu carro é mais rápido que o seu",
         "9": "Você deveria ligar para ele",
         "10": "Embora ele estivesse cansado, decidiu terminar o projeto",
         "11": "b", "12": "d"
      }
    }
    """
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    whatsapp = data.get("whatsapp", "")
    answers = data.get("answers") or {}

    if not nome:
        return jsonify({"error": "Nome é obrigatório."}), 400
    if not answers:
        return jsonify({"error": "Nenhuma resposta enviada."}), 400

    try:
        graded = grade_all_answers(answers)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    score = compute_score(graded)
    record = save_result(nome, whatsapp, score)

    return jsonify({
        "resultado": score,
        "detalhes_questoes": graded,
        "registro_salvo": record,
    })


@app.post("/api/whatsapp")
def submit_whatsapp():
    """
    Body JSON esperado:
    {
      "id": 12,
      "whatsapp": "(81) 98765-4321",
      "aula_experimental": true,
      "analise_plano": false
    }

    Usado pela tela de resultado: o aluno já viu o resultado e, se quiser,
    deixa o WhatsApp depois, sem precisar refazer o teste.
    """
    data = request.get_json(silent=True) or {}
    try:
        record_id = int(data.get("id"))
    except (TypeError, ValueError):
        return jsonify({"error": "id do registro inválido."}), 400

    whatsapp = (data.get("whatsapp") or "").strip()
    if not whatsapp:
        return jsonify({"error": "Informe um WhatsApp."}), 400

    interesses = {
        "aula_experimental": bool(data.get("aula_experimental")),
        "analise_plano": bool(data.get("analise_plano")),
    }

    record = update_whatsapp(record_id, whatsapp, interesses)
    if record is None:
        return jsonify({"error": "Registro não encontrado."}), 404

    return jsonify({"registro_salvo": record})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port)
