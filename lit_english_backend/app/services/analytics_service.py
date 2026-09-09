"""Telemetria, custos e agregações do painel AI Analytics & Cost Monitoring.

A aplicação registra o consumo por turno no banco. Custos Azure são sincronizados
em lote, uma vez por dia, pelo Cost Management (ActualCost). O primeiro startup
faz uma sincronização imediatamente quando as credenciais Azure estão disponíveis.
"""
from __future__ import annotations

import asyncio
import logging
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AIUsageLog, AzureCostSnapshot

logger = logging.getLogger("lit.analytics")

AZURE_API_VERSION = os.getenv("AZURE_COST_API_VERSION", "2026-06-01")
AZURE_SCOPE = os.getenv("AZURE_COST_SCOPE", "")
DAILY_SYNC_HOURS = int(os.getenv("ANALYTICS_COST_SYNC_HOURS", "24"))
INITIAL_COST_LOOKBACK_DAYS = int(os.getenv("ANALYTICS_INITIAL_LOOKBACK_DAYS", "90"))

# GPT-OSS 120B public on-demand rates currently published by Groq.
# They are configurable because provider pricing can change.
GROQ_INPUT_USD_PER_MILLION = float(os.getenv("GROQ_INPUT_USD_PER_MILLION", "0.15"))
GROQ_OUTPUT_USD_PER_MILLION = float(os.getenv("GROQ_OUTPUT_USD_PER_MILLION", "0.60"))


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * p / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def _period_dates(start: date | None, end: date | None) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    return start or today.replace(day=1), end or today


def _groq_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1_000_000) * GROQ_INPUT_USD_PER_MILLION + (output_tokens / 1_000_000) * GROQ_OUTPUT_USD_PER_MILLION


async def fetch_usd_brl() -> float:
    """Obtém a cotação USD/BRL usada apenas para consolidar o dashboard.

    O valor é buscado uma vez por sincronização diária, nunca por carregamento
    do dashboard. Se a cotação falhar, retornamos 0 e mantemos custos nativos.
    """
    url = "https://api.frankfurter.app/latest?from=USD&to=BRL"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            value = float(response.json()["rates"]["BRL"])
            if value > 0:
                return value
    except Exception:
        logger.warning("Não foi possível obter USD/BRL para o custo Groq", exc_info=True)
    return 0.0


async def fetch_azure_costs(start: date, end: date) -> list[dict]:
    """Consulta Azure Cost Management no escopo configurado.

    Usa DefaultAzureCredential, que funciona com AZURE_CLIENT_ID/
    AZURE_TENANT_ID/AZURE_CLIENT_SECRET em produção e com Azure CLI/Managed
    Identity nos ambientes suportados.
    """
    scope = AZURE_SCOPE.strip()
    if not scope:
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "").strip()
        if not subscription_id:
            raise RuntimeError("AZURE_SUBSCRIPTION_ID ou AZURE_COST_SCOPE não configurado")
        scope = f"subscriptions/{subscription_id}"
    scope = scope.strip("/")

    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise RuntimeError("Instale azure-identity para habilitar custos Azure") from exc

    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    token = credential.get_token("https://management.azure.com/.default")
    url = f"https://management.azure.com/{scope}/providers/Microsoft.CostManagement/query"
    params = {"api-version": AZURE_API_VERSION}
    body = {
        "type": "ActualCost",
        "timeframe": "Custom",
        "timePeriod": {
            "from": f"{start.isoformat()}T00:00:00Z",
            "to": f"{end.isoformat()}T23:59:59Z",
        },
        "dataset": {
            "granularity": "Daily",
            "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
            "grouping": [
                {"name": "ServiceName", "type": "Dimension"},
                {"name": "Meter", "type": "Dimension"},
            ],
        },
    }
    headers = {"Authorization": f"Bearer {token.token}", "Content-Type": "application/json"}

    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(url, params=params, json=body, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"Azure Cost Management {response.status_code}: {response.text[:800]}")
        data = response.json().get("properties", {})
        columns = [c["name"] for c in data.get("columns", [])]
        for raw in data.get("rows", []):
            item = dict(zip(columns, raw))
            cost = float(item.get("PreTaxCost") or item.get("Cost") or 0)
            if not cost:
                continue
            raw_date = str(item.get("UsageDate") or item.get("Date") or item.get("UsageDateTime") or "")
            if raw_date.isdigit() and len(raw_date) == 8:
                raw_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
            rows.append({
                "date": raw_date[:10],
                "service_name": str(item.get("ServiceName") or "Azure").strip(),
                "meter": str(item.get("Meter") or "").strip(),
                "cost": cost,
                "currency": str(item.get("Currency") or "USD"),
            })
    credential.close()
    return rows


def classify_azure_service(service_name: str, meter: str) -> str:
    text = f"{service_name} {meter}".lower()
    if "speech" in text and any(x in text for x in ("recognition", "transcription", "speech to text", "stt")):
        return "STT (Azure)"
    if "speech" in text and any(x in text for x in ("synthesis", "text to speech", "tts", "neural")):
        return "TTS (Azure)"
    if "cognitive" in text or "speech" in text:
        return "Azure Speech"
    return "Infraestrutura"


def save_azure_rows(db: Session, rows: list[dict], synced_at: datetime | None = None) -> int:
    synced_at = synced_at or datetime.utcnow()
    count = 0
    for row in rows:
        try:
            day = date.fromisoformat(row["date"])
        except Exception:
            continue
        existing = (
            db.query(AzureCostSnapshot)
            .filter(
                AzureCostSnapshot.usage_date == day,
                AzureCostSnapshot.service_name == row["service_name"],
                AzureCostSnapshot.meter == row["meter"],
                AzureCostSnapshot.currency == row["currency"],
            )
            .first()
        )
        if existing:
            existing.cost = row["cost"]
            existing.synced_at = synced_at
        else:
            db.add(AzureCostSnapshot(
                usage_date=day,
                service_name=row["service_name"],
                meter=row["meter"],
                cost=row["cost"],
                currency=row["currency"],
                synced_at=synced_at,
            ))
        count += 1
    db.commit()
    return count


def sync_azure_costs(db: Session, lookback_days: int | None = None) -> dict:
    """Synchronous wrapper used by the scheduler/startup and admin endpoint."""
    import asyncio
    today = datetime.now(timezone.utc).date()
    days = lookback_days if lookback_days is not None else INITIAL_COST_LOOKBACK_DAYS
    start = today - timedelta(days=max(0, days - 1))
    rows = asyncio.run(fetch_azure_costs(start, today))
    count = save_azure_rows(db, rows)
    return {"rows": count, "start": start.isoformat(), "end": today.isoformat()}


def build_overview(db: Session, start: date | None = None, end: date | None = None) -> dict:
    start, end = _period_dates(start, end)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())

    logs = (
        db.query(AIUsageLog)
        .filter(AIUsageLog.created_at >= start_dt, AIUsageLog.created_at < end_dt)
        .all()
    )
    active_students = len({x.student_id for x in logs if x.student_id is not None})
    total_ms = [float(x.total_ms or 0) for x in logs if x.total_ms is not None]
    stt_ms = [float(x.stt_ms or 0) for x in logs if x.stt_ms is not None]
    llm_ms = [float(x.llm_ms or 0) for x in logs if x.llm_ms is not None]
    tts_ms = [float(x.tts_ms or 0) for x in logs if x.tts_ms is not None]
    input_tokens = sum(int(x.input_tokens or 0) for x in logs)
    output_tokens = sum(int(x.output_tokens or 0) for x in logs)
    total_tokens = input_tokens + output_tokens
    audio_seconds = sum(float(x.audio_seconds or 0) for x in logs)
    fallback_count = sum(1 for x in logs if x.stt_fallback)
    error_count = sum(1 for x in logs if x.status != "success")

    # Azure actual cost already synchronized in the database.
    azure_rows = (
        db.query(AzureCostSnapshot)
        .filter(AzureCostSnapshot.usage_date >= start, AzureCostSnapshot.usage_date <= end)
        .all()
    )
    cost_by_service: dict[str, float] = defaultdict(float)
    currency = next((r.currency for r in azure_rows), "BRL")
    for row in azure_rows:
        cost_by_service[classify_azure_service(row.service_name, row.meter)] += float(row.cost or 0)

    groq_usd = _groq_cost_usd(input_tokens, output_tokens)
    fx = 0.0
    if currency.upper() == "USD":
        # Same-currency total can be shown directly.
        groq_display = groq_usd
        total_cost = sum(cost_by_service.values()) + groq_usd
    elif currency.upper() == "BRL":
        # Groq bills in USD; convert once per daily sync using the stored daily
        # FX snapshot so the dashboard can show one BRL total without calling
        # an FX provider every time the professor opens the page.
        fx_row = (
            db.query(AzureCostSnapshot)
            .filter(AzureCostSnapshot.fx_usd_brl.isnot(None), AzureCostSnapshot.usage_date >= start, AzureCostSnapshot.usage_date <= end)
            .order_by(AzureCostSnapshot.usage_date.desc())
            .first()
        )
        fx = float(fx_row.fx_usd_brl or 0) if fx_row else 0.0
        groq_display = groq_usd * fx if fx else 0.0
        total_cost = sum(cost_by_service.values()) + groq_display
    else:
        # Unknown/non-BRL Azure billing currency: do not invent a conversion.
        groq_display = 0.0
        total_cost = sum(cost_by_service.values())

    if groq_usd:
        cost_by_service["LLM (Groq)"] += groq_display
    cost_total = sum(cost_by_service.values())
    if cost_total <= 0 and not logs:
        cost_total = 0.0

    service_counts = {
        "stt": sum(1 for x in logs if x.stt_provider),
        "llm": sum(1 for x in logs if x.llm_provider),
        "tts": sum(1 for x in logs if x.tts_provider),
        "other": error_count,
    }

    daily = defaultdict(lambda: {"stt": 0, "llm": 0, "tts": 0, "other": 0})
    daily_latency = defaultdict(lambda: {"stt": [], "llm": [], "tts": [], "total": [], "upload": []})
    daily_tokens = defaultdict(list)
    for x in logs:
        key = x.created_at.date().isoformat()
        if x.stt_provider: daily[key]["stt"] += 1
        if x.llm_provider: daily[key]["llm"] += 1
        if x.tts_provider: daily[key]["tts"] += 1
        if x.status != "success": daily[key]["other"] += 1
        daily_latency[key]["stt"].append(float(x.stt_ms or 0) / 1000)
        daily_latency[key]["llm"].append(float(x.llm_ms or 0) / 1000)
        daily_latency[key]["tts"].append(float(x.tts_ms or 0) / 1000)
        daily_latency[key]["total"].append(float(x.total_ms or 0) / 1000)
        daily_latency[key]["upload"].append(float(x.upload_ms or 0) / 1000)
        daily_tokens[key].append(int(x.output_tokens or 0))

    day = start
    labels, series = [], {"stt": [], "llm": [], "tts": [], "other": []}
    latency_series = {"stt": [], "llm": [], "tts": [], "total": []}
    token_series = []
    while day <= end:
        key = day.isoformat()
        labels.append(day.strftime("%d/%m"))
        for k in series: series[k].append(daily[key][k])
        for k in latency_series:
            vals = daily_latency[key][k]
            latency_series[k].append(statistics.fmean(vals) if vals else 0)
        token_series.append(statistics.fmean(daily_tokens[key]) if daily_tokens[key] else 0)
        day += timedelta(days=1)

    return {
        "start": start.isoformat(), "end": end.isoformat(),
        "currency": currency,
        "activeStudents": active_students,
        "apiCalls": len(logs),
        "totalCost": cost_total,
        "azureCost": sum(cost_by_service[k] for k in cost_by_service if k != "LLM (Groq)"),
        "groqCostUsd": groq_usd,
        "groqCostDisplay": groq_display,
        "avgLatency": (statistics.fmean(total_ms) / 1000) if total_ms else 0,
        "tokens": total_tokens,
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "audioSeconds": audio_seconds,
        "fallbackRate": (fallback_count / len(logs) * 100) if logs else 0,
        "errorRate": (error_count / len(logs) * 100) if logs else 0,
        "percentiles": {"p50": _percentile(total_ms, 50)/1000, "p90": _percentile(total_ms, 90)/1000, "p95": _percentile(total_ms, 95)/1000, "p99": _percentile(total_ms, 99)/1000},
        "sttPercentiles": {"p50": _percentile(stt_ms,50)/1000, "p90": _percentile(stt_ms,90)/1000, "p95": _percentile(stt_ms,95)/1000, "p99": _percentile(stt_ms,99)/1000},
        "llmPercentiles": {"p50": _percentile(llm_ms,50)/1000, "p90": _percentile(llm_ms,90)/1000, "p95": _percentile(llm_ms,95)/1000, "p99": _percentile(llm_ms,99)/1000},
        "ttsPercentiles": {"p50": _percentile(tts_ms,50)/1000, "p90": _percentile(tts_ms,90)/1000, "p95": _percentile(tts_ms,95)/1000, "p99": _percentile(tts_ms,99)/1000},
        "serviceCounts": service_counts,
        "dailyCalls": {"labels": labels, **series},
        "latencySeries": {"labels": labels, **latency_series},
        "tokenSeries": {"labels": labels, "output": token_series},
        "tokenPercentiles": {"p50": _percentile([float(x.output_tokens or 0) for x in logs], 50), "p90": _percentile([float(x.output_tokens or 0) for x in logs], 90), "p95": _percentile([float(x.output_tokens or 0) for x in logs], 95), "p99": _percentile([float(x.output_tokens or 0) for x in logs], 99)},
        "waterfall": [
            ["Upload", (statistics.fmean([float(x.upload_ms or 0) for x in logs]) / 1000 if logs else 0)],
            ["STT", (statistics.fmean(stt_ms) / 1000 if stt_ms else 0)],
            ["LLM", (statistics.fmean(llm_ms) / 1000 if llm_ms else 0)],
            ["TTS", (statistics.fmean(tts_ms) / 1000 if tts_ms else 0)],
            ["Overhead", max(0, (statistics.fmean(total_ms) / 1000 if total_ms else 0) - (statistics.fmean([float(x.upload_ms or 0) for x in logs]) / 1000 if logs else 0) - (statistics.fmean(stt_ms) / 1000 if stt_ms else 0) - (statistics.fmean(llm_ms) / 1000 if llm_ms else 0) - (statistics.fmean(tts_ms) / 1000 if tts_ms else 0))],
            ["Total", (statistics.fmean(total_ms) / 1000 if total_ms else 0)],
        ],
        "costServices": [
            {"name": name, "value": value, "share": (value / cost_total * 100 if cost_total else 0), "tone": tone}
            for (name, value), tone in zip(
                [(name, value) for name, value in cost_by_service.items() if value > 0],
                ["burgundy", "black", "gray", "pale", "black", "gray"],
            )
        ],
        "lastCostSync": db.query(func.max(AzureCostSnapshot.synced_at)).scalar(),
    }


def record_usage(db: Session, **kwargs) -> None:
    db.add(AIUsageLog(**kwargs))
    db.commit()


async def daily_cost_sync_loop(session_factory) -> None:
    """Primeiro sync imediato; depois, no máximo uma vez a cada 24h."""
    await asyncio.sleep(1)
    while True:
        try:
            db = session_factory()
            try:
                last_sync = db.query(func.max(AzureCostSnapshot.synced_at)).scalar()
                should_sync = last_sync is None or (datetime.utcnow() - last_sync).total_seconds() >= DAILY_SYNC_HOURS * 3600
                if should_sync:
                    try:
                        await asyncio.to_thread(sync_azure_costs, db, INITIAL_COST_LOOKBACK_DAYS if last_sync is None else 7)
                        # Persist one current FX snapshot alongside the newest cost row.
                        fx = await fetch_usd_brl()
                        if fx:
                            newest = db.query(AzureCostSnapshot).order_by(AzureCostSnapshot.usage_date.desc()).first()
                            if newest:
                                newest.fx_usd_brl = fx
                                db.commit()
                    except Exception:
                        logger.warning("Sincronização diária do Azure falhou; mantendo último snapshot", exc_info=True)
            finally:
                db.close()
        except Exception:
            logger.exception("Erro no loop diário de analytics")
        await asyncio.sleep(3600)
