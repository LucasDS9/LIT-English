"""
Motor de transcrição de áudio — LIT English

Mantém apenas o pipeline de transcrição (Faster-Whisper) usado pelo
exercício "Speak it!" (app/routers/exercises.py). A feature standalone de
prática de pronúncia (frases de prática, comparação fonética, histórico)
foi removida — uma nova página de pronúncia será implementada depois.

IMPORTANTE: `transcribe()` é importada por app/routers/exercises.py para
corrigir o exercício de fala. Não remover esta função.
"""
import os
import tempfile


# ---------------------------------------------------------------------------
# Lazy loader do modelo Whisper
# ---------------------------------------------------------------------------
_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        except ImportError:
            from fastapi import HTTPException
            raise HTTPException(status_code=500,
                detail="faster-whisper não está instalado.")
    return _whisper_model


# ---------------------------------------------------------------------------
# Áudio → texto (Whisper)
# ---------------------------------------------------------------------------

def convert_audio_to_wav(input_path: str) -> str:
    """
    Converte para WAV 16kHz mono usando ffmpeg.
    Tenta localizar o ffmpeg mesmo quando não está no PATH padrão do Windows.
    Retorna o input_path original se a conversão falhar (Whisper aceita webm direto).
    """
    import subprocess
    import shutil

    output_path = input_path + "_conv.wav"

    # Procura ffmpeg no PATH e em locais comuns do Windows
    ffmpeg_cmd = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg_cmd:
        # Tenta caminhos comuns no Windows
        candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for c in candidates:
            if os.path.exists(c):
                ffmpeg_cmd = c
                break

    if not ffmpeg_cmd:
        # ffmpeg não encontrado — Whisper consegue lidar com webm diretamente
        return input_path

    try:
        r = subprocess.run(
            [ffmpeg_cmd, "-y", "-i", input_path,
             "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_path],
            capture_output=True, timeout=30,
        )
        return output_path if r.returncode == 0 and os.path.exists(output_path) else input_path
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return input_path


def transcribe(audio_bytes: bytes, language: str) -> str:
    model = get_whisper_model()
    lang_map = {"english": "en", "german": "de", "french": "fr", "italian": "it"}
    whisper_lang = lang_map.get(language, "en")

    # Salva o áudio recebido num arquivo temporário
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    wav_path = convert_audio_to_wav(tmp_path)
    # wav_path pode ser igual a tmp_path se o ffmpeg não estiver disponível

    try:
        segments, _ = model.transcribe(
            wav_path,
            language=whisper_lang,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        # Remove os arquivos temporários com segurança
        for path in set([tmp_path, wav_path]):
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
