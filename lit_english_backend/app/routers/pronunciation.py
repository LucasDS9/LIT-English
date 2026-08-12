"""
Motor de transcrição e avaliação de pronúncia — LIT English

Usa Azure Speech (mesmo padrão do Groq: variáveis de ambiente + chamada direta).
  - LIT_SPEECH_API    → chave do recurso Azure Speech
  - LIT_SPEECH_REGION → região (ex.: brazilsouth, eastus)

Se Azure não estiver configurado, cai para Faster-Whisper local (dev).

`transcribe()` e `assess_pronunciation()` são usados por exercícios, flashcards
e a tela Aprender.
"""
import json
import logging
import os
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

_whisper_model = None

LANGUAGE_LOCALES = {
    "english": "en-US",
    "italian": "it-IT",
    "french": "fr-FR",
    "ingles": "en-US",
    "italiano": "it-IT",
    "frances": "fr-FR",
}


def _azure_speech_key() -> str | None:
    key = (os.environ.get("LIT_SPEECH_API") or "").strip()
    return key or None


def _azure_speech_region() -> str | None:
    for env_key in ("LIT_SPEECH_REGION", "AZURE_SPEECH_REGION"):
        region = (os.environ.get(env_key) or "").strip()
        if region:
            return region
    return None


def _azure_available() -> bool:
    return bool(_azure_speech_key() and _azure_speech_region())


def _resolve_locale(language: str) -> str:
    code = (language or "english").strip().lower()
    return LANGUAGE_LOCALES.get(code, "en-US")


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        except ImportError:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=500,
                detail="faster-whisper não está instalado.",
            )
    return _whisper_model


def convert_audio_to_wav(input_path: str) -> str:
    import shutil
    import subprocess

    output_path = input_path + "_conv.wav"
    ffmpeg_cmd = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg_cmd:
        candidates = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                ffmpeg_cmd = candidate
                break

    if not ffmpeg_cmd:
        return input_path

    try:
        result = subprocess.run(
            [
                ffmpeg_cmd, "-y", "-i", input_path,
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
                output_path,
            ],
            capture_output=True,
            timeout=30,
        )
        return output_path if result.returncode == 0 and os.path.exists(output_path) else input_path
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return input_path


def _build_reason(score: int | None, word_scores: list[dict[str, Any]] | None) -> str:
    if score is None:
        return "Áudio reconhecido com sucesso."
    if score >= 80:
        return "Sua pronúncia está muito boa — continue assim."
    if score >= 60:
        return "Boa tentativa — refine alguns sons e o ritmo da frase."
    if word_scores:
        weakest = min(word_scores, key=lambda item: item["score"])
        return f"Preste atenção ao som de '{weakest['word']}' e ao ritmo da frase."
    return "Preste atenção ao ritmo da frase e aos sons de cada palavra."


def _recognize_azure(wav_path: str, locale: str, reference_text: str | None = None) -> dict[str, Any]:
    import azure.cognitiveservices.speech as speechsdk

    speech_config = speechsdk.SpeechConfig(
        subscription=_azure_speech_key(),
        region=_azure_speech_region(),
    )
    speech_config.speech_recognition_language = locale

    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    if reference_text:
        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=reference_text,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.Word,
            enable_miscue=True,
        )
        pronunciation_config.apply_to(recognizer)

    result = recognizer.recognize_once()

    if result.reason != speechsdk.ResultReason.RecognizedSpeech:
        detail = result.cancellation_details.error_details if result.cancellation_details else result.reason.name
        raise RuntimeError(f"Azure Speech não reconheceu o áudio: {detail}")

    payload: dict[str, Any] = {
        "transcribed_text": (result.text or "").strip(),
        "score": None,
        "word_scores": None,
        "reason": None,
    }

    json_result = result.properties.get(
        speechsdk.PropertyId.SpeechServiceResponse_JsonResult
    )
    if not json_result:
        payload["reason"] = _build_reason(None, None)
        return payload

    try:
        data = json.loads(json_result)
    except json.JSONDecodeError:
        payload["reason"] = _build_reason(None, None)
        return payload

    nbest = (data.get("NBest") or [{}])[0]
    if not payload["transcribed_text"]:
        payload["transcribed_text"] = (
            nbest.get("Display")
            or nbest.get("Lexical")
            or nbest.get("ITN")
            or ""
        ).strip()

    pron = nbest.get("PronunciationAssessment") or {}
    score_raw = pron.get("PronScore", pron.get("AccuracyScore"))
    if score_raw is not None:
        payload["score"] = max(0, min(100, int(round(float(score_raw)))))

    word_scores = []
    for word_info in nbest.get("Words") or []:
        word = (word_info.get("Word") or "").strip()
        if not word:
            continue
        word_assessment = word_info.get("PronunciationAssessment") or {}
        word_score_raw = word_assessment.get("AccuracyScore")
        if word_score_raw is None:
            continue
        word_scores.append({
            "word": word,
            "score": max(0, min(100, int(round(float(word_score_raw))))),
        })
    if word_scores:
        payload["word_scores"] = word_scores

    payload["reason"] = _build_reason(payload["score"], word_scores)
    return payload


def _prepare_audio_paths(audio_bytes: bytes) -> tuple[str, str]:
    suffix = ".webm"
    if audio_bytes[:4] == b"OggS":
        suffix = ".ogg"
    elif audio_bytes[:4] == b"RIFF":
        suffix = ".wav"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    wav_path = convert_audio_to_wav(tmp_path)
    return tmp_path, wav_path


def _cleanup_paths(*paths: str | None) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass


def _azure_process(audio_bytes: bytes, language: str, reference_text: str | None = None) -> dict[str, Any]:
    locale = _resolve_locale(language)
    tmp_path, wav_path = _prepare_audio_paths(audio_bytes)
    try:
        return _recognize_azure(wav_path, locale, reference_text=reference_text)
    finally:
        _cleanup_paths(tmp_path, wav_path if wav_path != tmp_path else None)


def _transcribe_whisper(audio_bytes: bytes, language: str) -> str:
    model = get_whisper_model()
    lang_map = {"english": "en", "german": "de", "french": "fr", "italian": "it"}
    whisper_lang = lang_map.get(language, "en")

    tmp_path, wav_path = _prepare_audio_paths(audio_bytes)
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
        _cleanup_paths(tmp_path, wav_path if wav_path != tmp_path else None)


def transcribe(audio_bytes: bytes, language: str) -> str:
    """Áudio → texto. Usa Azure Speech quando LIT_SPEECH_API estiver configurada."""
    if _azure_available():
        try:
            result = _azure_process(audio_bytes, language)
            return result["transcribed_text"]
        except Exception as exc:
            logger.exception("Falha no Azure Speech (transcribe), usando Whisper: %s", exc)
    elif _azure_speech_key() and not _azure_speech_region():
        logger.warning("LIT_SPEECH_API definida, mas LIT_SPEECH_REGION ausente — usando Whisper.")

    return _transcribe_whisper(audio_bytes, language)


def assess_pronunciation(
    audio_bytes: bytes,
    language: str,
    reference_text: str,
) -> dict[str, Any]:
    """
    Transcrição + score de pronúncia via Azure Pronunciation Assessment.
    Sem Azure configurado, cai para Whisper (sem score).
    """
    reference = (reference_text or "").strip()
    if _azure_available() and reference:
        try:
            return _azure_process(audio_bytes, language, reference_text=reference)
        except Exception as exc:
            logger.exception("Falha no Azure Speech (assess), usando Whisper: %s", exc)
    elif _azure_speech_key() and not _azure_speech_region():
        logger.warning("LIT_SPEECH_API definida, mas LIT_SPEECH_REGION ausente — usando Whisper.")

    transcribed_text = _transcribe_whisper(audio_bytes, language)
    return {
        "transcribed_text": transcribed_text,
        "score": None,
        "word_scores": None,
        "reason": None,
    }
