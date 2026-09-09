"""AI Analytics & Cost Monitoring — somente professor."""
from __future__ import annotations

from datetime import date, timedelta
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_professor
from app.database import get_db
from app.models import AzureCostSnapshot, User
from app.services.analytics_service import build_overview, sync_azure_costs

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Data inválida: {value}") from exc


@router.get("/overview")
def analytics_overview(
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_professor),
):
    today = date.today()
    start_date = _parse_date(start, today.replace(day=1))
    end_date = _parse_date(end, today)
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="O fim do período deve ser posterior ao início.")

    # Primeiro acesso: garante que o professor não veja um dashboard vazio
    # esperando o loop de startup. Depois disso, as consultas Azure ficam
    # somente no sincronizador diário.
    if db.query(AzureCostSnapshot.id).first() is None and (os.getenv("AZURE_SUBSCRIPTION_ID") or os.getenv("AZURE_COST_SCOPE")):
        try:
            sync_azure_costs(db)
        except Exception:
            # Telemetria continua disponível mesmo sem Cost Management.
            pass

    current = build_overview(db, start_date, end_date)
    period_days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    previous = build_overview(db, previous_start, previous_end)

    def change(current_value, previous_value):
        if not previous_value:
            return 0
        return round(((current_value - previous_value) / previous_value) * 100, 1)

    current["changes"] = {
        "activeStudents": change(current["activeStudents"], previous["activeStudents"]),
        "apiCalls": change(current["apiCalls"], previous["apiCalls"]),
        "totalCost": change(current["totalCost"], previous["totalCost"]),
        "avgLatency": change(current["avgLatency"], previous["avgLatency"]),
        "tokens": change(current["tokens"], previous["tokens"]),
    }
    if current.get("lastCostSync"):
        current["lastCostSync"] = current["lastCostSync"].isoformat()
    current["previousPeriod"] = {"start": previous_start.isoformat(), "end": previous_end.isoformat()}
    return current


@router.post("/costs/sync")
def analytics_cost_sync(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_professor),
):
    """Sincronização manual apenas para o professor; não é usada pelo frontend."""
    try:
        return {"ok": True, **sync_azure_costs(db)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao sincronizar custos Azure: {exc}") from exc
