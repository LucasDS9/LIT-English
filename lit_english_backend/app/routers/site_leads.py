"""
Leads do site institucional (lit_english_frontend/index.html) — landing page
pública, sem login. Dois pontos de captura caem aqui:

  - Botão "Comece Agora"     -> modal "Agendar Aula Experimental"
    (source="comece_agora", preenche nivel/objetivo)
  - Seção "Entre em Contato" -> formulário de contato
    (source="contato", preenche mensagem)

O POST de captura é público (o visitante do site não faz login) — só as
rotas usadas pelo painel do professor (listar, apagar) exigem login de
professor, seguindo o mesmo padrão do router de level_test.py.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_professor
from app.database import get_db
from app.models import SiteLead, User
from app.schemas import SiteLeadIn, SiteLeadOut

router = APIRouter(prefix="/site-leads", tags=["Leads do Site"])

VALID_SOURCES = {"comece_agora", "contato"}


def _normalize_whatsapp(raw: str) -> str:
    """Mesma normalização usada em level_test.py: DDD + 9 + 8 dígitos."""
    digits = re.sub(r"\D", "", raw or "")

    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    if len(digits) == 10:
        digits = digits[:2] + "9" + digits[2:]

    return digits


@router.post("/submit", response_model=SiteLeadOut)
def submit_lead(payload: SiteLeadIn, db: Session = Depends(get_db)):
    """Salva um lead vindo do "Comece Agora" ou do "Entre em Contato"."""
    if payload.source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail="Origem de lead inválida.")
    if not payload.nome.strip():
        raise HTTPException(status_code=400, detail="Nome é obrigatório.")

    data = payload.model_dump()
    data["nome"] = data["nome"].strip()
    data["whatsapp"] = _normalize_whatsapp(data.get("whatsapp", ""))
    record = SiteLead(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("", response_model=list[SiteLeadOut])
def list_leads(
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Lista os leads do site, mais recentes primeiro (para o painel do
    professor)."""
    return db.query(SiteLead).order_by(SiteLead.created_at.desc()).all()


@router.delete("/{lead_id}", status_code=204)
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    _professor: User = Depends(get_current_professor),
):
    """Apaga um lead do site."""
    record = db.query(SiteLead).filter(SiteLead.id == lead_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    db.delete(record)
    db.commit()
    return None
