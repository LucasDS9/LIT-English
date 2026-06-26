"""
Utilitários de fuso horário (Brasília, UTC-3 permanente desde 2019).
O banco armazena datetimes UTC naive; comparações de "dia" usam horário de Brasília.
"""
from datetime import datetime, timedelta, timezone

BR_OFFSET = timezone(timedelta(hours=-3))


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_brazil(dt: datetime) -> datetime:
    """Converte datetime UTC naive para aware em Brasília (UTC-3)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BR_OFFSET)


def brazil_date_key(dt: datetime) -> str:
    """Chave YYYY-MM-DD no fuso de Brasília."""
    return to_brazil(dt).strftime("%Y-%m-%d")


def start_of_next_day_brazil_utc() -> datetime:
    """Meia-noite do próximo dia em Brasília, retornado como UTC naive."""
    now_br = datetime.now(BR_OFFSET)
    tomorrow_br = (now_br + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return tomorrow_br.astimezone(timezone.utc).replace(tzinfo=None)
