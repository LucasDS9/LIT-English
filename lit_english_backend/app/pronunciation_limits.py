"""
Limites de uso da prática opcional de pronúncia (Azure Speech free tier).

Cada teste no botão "Pronunciar" em Revisar conta 1 tentativa.
Exercícios obrigatórios de fala (submit-speak) não passam por aqui.
"""
import logging
import os
import re
import shutil
import subprocess
import tempfile

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import PronunciationAttemptLog

logger = logging.getLogger(__name__)

PRONUNCIATION_MAX_SECONDS = 5
# Tolerância para imprecisão de container/codec na duração medida.
DURATION_TOLERANCE_SECONDS = 0.6


def _guess_suffix(audio_bytes: bytes) -> str:
    if audio_bytes[:4] == b"OggS":
        return ".ogg"
    if audio_bytes[:4] == b"RIFF":
        return ".wav"
    return ".webm"


def _ffprobe_duration(ffprobe: str, tmp_path: str, entries: str, select_stream: bool = False) -> float | None:
    cmd = [ffprobe, "-v", "error"]
    if select_stream:
        cmd += ["-select_streams", "a:0"]
    cmd += ["-show_entries", entries, "-of", "default=noprint_wrappers=1:nokey=1", tmp_path]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        return None
    value = result.stdout.strip().splitlines()[0].strip() if result.stdout.strip() else ""
    try:
        return float(value)
    except ValueError:
        return None


def _ffmpeg_decoded_duration(tmp_path: str) -> float | None:
    """Último recurso: decodifica o áudio de verdade e lê a duração tocada.

    Alguns containers gravados pelo MediaRecorder do navegador (webm/ogg
    fragmentado) não escrevem a duração no cabeçalho, então o `ffprobe`
    devolve "N/A" tanto para `format=duration` quanto para `stream=duration`
    -- daí o aviso no log. Como isso não bloqueava nada (a função já
    devolvia None e a checagem de limite era simplesmente pulada), o único
    problema real era o log ruidoso. Esse fallback decodifica o áudio de
    ponta a ponta com `ffmpeg` (sem gravar nada, `-f null -`) e lê a duração
    real tocada no resumo que ele imprime ao final -- funciona mesmo sem
    duração no cabeçalho do container.
    """
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        return None
    try:
        result = subprocess.run(
            [ffmpeg, "-v", "error", "-i", tmp_path, "-map", "0:a:0", "-f", "null", "-"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr or "")
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def audio_duration_seconds(audio_bytes: bytes) -> float | None:
    """Duração do áudio em segundos. None se não for possível medir de jeito nenhum."""
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=_guess_suffix(audio_bytes), delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # 1) Duração do container (rápido, funciona na maioria dos casos).
        duration = _ffprobe_duration(ffprobe, tmp_path, "format=duration")
        if duration is not None:
            return duration

        # 2) Alguns containers só têm a duração no stream, não no formato.
        duration = _ffprobe_duration(ffprobe, tmp_path, "stream=duration", select_stream=True)
        if duration is not None:
            return duration

        # 3) Container sem duração no cabeçalho (comum em webm/ogg gravados
        # direto do navegador): decodifica de verdade pra medir.
        duration = _ffmpeg_decoded_duration(tmp_path)
        if duration is not None:
            return duration

        logger.info("Duração do áudio não pôde ser medida por nenhum método; seguindo sem checagem de limite.")
        return None
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("Não foi possível medir duração do áudio: %s", exc)
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def enforce_optional_pronunciation_limits(db: Session, student_id: int, audio_bytes: bytes) -> None:
    """Valida a duração máxima antes de chamar Azure/Whisper."""
    duration = audio_duration_seconds(audio_bytes)
    if duration is not None and duration > PRONUNCIATION_MAX_SECONDS + DURATION_TOLERANCE_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Áudio muito longo. Grave no máximo {PRONUNCIATION_MAX_SECONDS} segundos.",
        )


def log_pronunciation_attempt(db: Session, student_id: int) -> None:
    db.add(PronunciationAttemptLog(student_id=student_id))
    db.commit()
