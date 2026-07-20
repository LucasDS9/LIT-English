"""
Teste de Nivelamento (lit_english_teste_ingles) — leads.

O app do teste é público (o aluno não faz login), então as rotas de
gravação (submit / whatsapp) não exigem autenticação — só as rotas usadas
pelo painel do professor (contagem, leads, apagar) exigem login de
professor.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_professor
from app.database import get_db
from app.models import LevelTestResult, User
from app.schemas import LevelTestResultIn, LevelTestResultOut, LevelTestWhatsappIn

router = APIRouter(prefix="/level-test", tags=["Teste de Nivelamento"])


def _normalize_whatsapp(raw: str) -> str:
    """
    Normaliza o número para o formato xx9xxxxxxxx (DDD + 9 + 8 dígitos,
    11 dígitos no total, só números).

    - Remove qualquer caractere que não seja dígito (espaços, parênteses,
      traços, "+").
    - Remove o código do país (55) se vier junto.
    - Se vier sem o 9 (DDD + 8 dígitos = 10 dígitos), insere o 9
      automaticamente depois do DDD.
    """
    digits = re.sub(r"\D", "", raw or "")

    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    if len(digits) == 10:
        digits = digits[:2] + "9" + digits[2:]

    return digits


@router.post("/submit", response_model=LevelTestResultOut)
def submit_result(payload: LevelTestResultIn, db: Session = Depends(get_db)):
    """Salva o resultado de um teste recém-corrigido (chamado pelo app Flask
    do teste, logo após calcular o nível do aluno)."""
    data = payload.model_dump()
    data["whatsapp"] = _normalize_whatsapp(data.get("whatsapp", ""))
    record = LevelTestResult(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{result_id}/whatsapp", response_model=LevelTestResultOut)
def submit_whatsapp(result_id: int, payload: LevelTestWhatsappIn, db: Session = Depends(get_db)):
    """Atualiza o WhatsApp (e os interesses marcados) de um resultado já
    salvo — usado quando o aluno deixa o número na tela de resultado."""
    record = db.query(LevelTestResult).filter(LevelTestResult.id == result_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Resultado não encontrado.")

    record.whatsapp = _normalize_whatsapp(payload.whatsapp)
    record.quer_aula_experimental = payload.quer_aula_experimental
    record.quer_analise_plano = payload.quer_analise_plano
    db.commit()
    db.refresh(record)
    return record


@router.get("/count")
def count_tests(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Quantos testes de nivelamento foram feitos ao todo (contando quem não
    deixou WhatsApp também) — só o número, pra dar uma noção de alcance."""
    total = db.query(func.count(LevelTestResult.id)).scalar() or 0
    return {"total": total}


@router.get("/leads", response_model=list[LevelTestResultOut])
def list_leads(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista os leads do teste de nivelamento: só quem terminou o teste E
    deixou o WhatsApp (é isso que interessa comercialmente ao professor).
    Mais recentes primeiro."""
    return (
        db.query(LevelTestResult)
        .filter(LevelTestResult.whatsapp.isnot(None), LevelTestResult.whatsapp != "")
        .order_by(LevelTestResult.created_at.desc())
        .all()
    )


@router.delete("/{result_id}", status_code=204)
def delete_lead(
    result_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Apaga um resultado/lead do teste de nivelamento."""
    record = db.query(LevelTestResult).filter(LevelTestResult.id == result_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Resultado não encontrado.")
    db.delete(record)
    db.commit()
    return None
