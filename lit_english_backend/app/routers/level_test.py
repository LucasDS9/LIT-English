"""
Teste de Nivelamento (lit_english_teste_ingles) — leads.

O app do teste é público (o aluno não faz login), então as rotas de
gravação (submit / whatsapp) não exigem autenticação — só a listagem dos
leads (GET /level-test/leads), usada no painel do professor, exige login
de professor.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_professor
from app.database import get_db
from app.models import LevelTestResult, User
from app.schemas import LevelTestResultIn, LevelTestResultOut, LevelTestWhatsappIn

router = APIRouter(prefix="/level-test", tags=["Teste de Nivelamento"])


@router.post("/submit", response_model=LevelTestResultOut)
def submit_result(payload: LevelTestResultIn, db: Session = Depends(get_db)):
    """Salva o resultado de um teste recém-corrigido (chamado pelo app Flask
    do teste, logo após calcular o nível do aluno)."""
    record = LevelTestResult(**payload.model_dump())
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

    record.whatsapp = payload.whatsapp
    record.quer_aula_experimental = payload.quer_aula_experimental
    record.quer_analise_plano = payload.quer_analise_plano
    db.commit()
    db.refresh(record)
    return record


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
