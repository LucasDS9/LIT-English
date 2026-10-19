"""
Validação de código promocional do cadastro.

Regra atual: o código tem exatamente 5 caracteres (quaisquer). Enquanto a
lista de códigos válidos não for definida, QUALQUER código de 5 caracteres é
aceito. Para passar a aceitar só alguns, defina a variável de ambiente
PROMO_CODES (no Railway: Variables) com os códigos separados por vírgula:

    PROMO_CODES=AB12C,XY99Z,LIT26

A comparação ignora maiúsculas/minúsculas. Não é preciso mexer no código.
"""
import os

PROMO_CODE_LENGTH = 5


def normalize_promo_code(code: str | None) -> str:
    return (code or "").strip()


def has_valid_format(code: str | None) -> bool:
    return len(normalize_promo_code(code)) == PROMO_CODE_LENGTH


def _configured_codes() -> set[str]:
    raw = os.environ.get("PROMO_CODES", "")
    return {c.strip().upper() for c in raw.split(",") if c.strip()}


def is_valid_promo_code(code: str | None) -> bool:
    """True se o código tem 5 caracteres e (quando houver lista) está nela."""
    if not has_valid_format(code):
        return False
    configured = _configured_codes()
    if not configured:  # lista ainda não definida → qualquer código de 5 caracteres
        return True
    return normalize_promo_code(code).upper() in configured
