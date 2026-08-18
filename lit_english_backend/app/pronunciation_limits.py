"""
Limites de uso da prática opcional de pronúncia (Azure Speech free tier).

Cada teste no botão "Pronunciar" em Revisar conta 1 tentativa.
Exercícios obrigatórios de fala (submit-speak) não passam por aqui.
"""
import logging
import os
import shutil
import subprocess
import tempfile

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import PronunciationAttemptLog
from app.timezone import start_of_day_brazil_utc

logger = logging.getLogger(__name__)

PRONUNCIATION_DAILY_LIMIT = 15
PRONUNCIATION_MAX_SECONDS = 5
# Tolerância para imprecisão de container/codec na duração medida.
DURATION_TOLERANCE_SECONDS = 0.6


def count_today_pronunciation_attempts(db: Session, student_id: int) -> int:
    day_start = start_of_day_brazil_utc()
    return (
        db.query(PronunciationAttemptLog)
        .filter(
            PronunciationAttemptLog.student_id == student_id,
            PronunciationAttemptLog.created_at >= day_start,
        )
        .count()
    )


def remaining_pronunciation_attempts(db: Session, student_id: int) -> int:
    return max(0, PRONUNCIATION_DAILY_LIMIT - count_today_pronunciation_attempts(db, student_id))


def _guess_suffix(audio_bytes: bytes) -> str:
    if audio_bytes[:4] == b"OggS":
        return ".ogg"
    if audio_bytes[:4] == b"RIFF":
        return ".wav"
    return ".webm"


def audio_duration_seconds(audio_bytes: bytes) -> float | None:
    """Duração do áudio em segundos (ffprobe). None se não for possível medir."""
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=_guess_suffix(audio_bytes), delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return None
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Não foi possível medir duração do áudio: %s", exc)
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def enforce_optional_pronunciation_limits(db: Session, student_id: int, audio_bytes: bytes) -> None:
    """Valida limite diário e duração máxima antes de chamar Azure/Whisper."""
    used = count_today_pronunciation_attempts(db, student_id)
    if used >= PRONUNCIATION_DAILY_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Limite diário de {PRONUNCIATION_DAILY_LIMIT} testes de pronúncia atingido. "
                "Volte amanhã."
            ),
        )

    duration = audio_duration_seconds(audio_bytes)
    if duration is not None and duration > PRONUNCIATION_MAX_SECONDS + DURATION_TOLERANCE_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Áudio muito longo. Grave no máximo {PRONUNCIATION_MAX_SECONDS} segundos.",
        )


def log_pronunciation_attempt(db: Session, student_id: int) -> None:
    db.add(PronunciationAttemptLog(student_id=student_id))
    db.commit()
