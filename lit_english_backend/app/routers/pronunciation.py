"""
Motor de transcrição e avaliação de pronúncia — LIT English

Variáveis de ambiente (Azure Speech):
  LIT_SPEECH_API    → chave (subscription key)
  LIT_SPEECH_REGION → região (ex.: brazilsouth, eastus)

`transcribe()` — speech-to-text (Azure; Whisper só como fallback em dev).
`assess_pronunciation()` — avaliação real via Azure Pronunciation Assessment
(Comprehensive). Nunca usa Whisper nem julgamento textual.
"""
import base64
import json
import logging
import os
import re
import tempfile
from typing import Any

import requests

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


class PronunciationAssessmentUnavailable(Exception):
    """Azure Speech indisponível ou resposta sem pontuação de pronúncia."""


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


def _split_reference_words(text: str) -> list[str]:
    return re.findall(r"\S+", (text or "").strip())


def _clamp_score(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def _align_word_scores(reference_text: str, azure_words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Alinha palavras do texto esperado com AccuracyScore / ErrorType da Azure."""
    ref_words = _split_reference_words(reference_text)
    if not ref_words:
        return []

    aligned: list[dict[str, Any]] = []
    for index, ref_word in enumerate(ref_words):
        if index < len(azure_words):
            word_info = azure_words[index]
            assessment = word_info.get("PronunciationAssessment") or {}
            score = _clamp_score(assessment.get("AccuracyScore"))
            aligned.append({
                "word": ref_word,
                "score": score if score is not None else 0,
                "error_type": assessment.get("ErrorType") or "None",
            })
        else:
            aligned.append({
                "word": ref_word,
                "score": 0,
                "error_type": "Omission",
            })
    return aligned


def _build_feedback(score: int, word_scores: list[dict[str, Any]]) -> tuple[str, str]:
    weak = sorted(
        [w for w in word_scores if w.get("score", 100) < 80],
        key=lambda item: item.get("score", 0),
    )

    if score >= 80:
        title = "Ótima pronúncia!"
        detail = "Sua pronúncia está clara e próxima do esperado."
    elif score >= 60:
        title = "Boa pronúncia!"
        if weak:
            quoted = ", ".join(f'"{w["word"]}"' for w in weak[:2])
            detail = f"Algumas palavras precisam de atenção, principalmente {quoted}."
        else:
            detail = "Boa base — refine o ritmo e os sons finais."
    else:
        title = "Tente novamente!"
        if weak:
            detail = f'Preste atenção ao som de "{weak[0]["word"]}" e ao ritmo da frase.'
        else:
            detail = "Tente falar mais devagar, acompanhando cada palavra."

    return title, detail


def _parse_azure_assessment_json(data: dict[str, Any], reference_text: str) -> dict[str, Any]:
    nbest = (data.get("NBest") or [{}])[0]
    pron = nbest.get("PronunciationAssessment") or {}

    transcribed_text = (
        nbest.get("Display")
        or nbest.get("Lexical")
        or nbest.get("ITN")
        or nbest.get("MaskedITN")
        or ""
    ).strip()

    score = _clamp_score(pron.get("PronScore"))
    if score is None:
        score = _clamp_score(pron.get("AccuracyScore"))

    azure_words = nbest.get("Words") or []
    word_scores = _align_word_scores(reference_text, azure_words)

    if score is None and word_scores:
        scores = [w["score"] for w in word_scores if w.get("score") is not None]
        if scores:
            score = int(round(sum(scores) / len(scores)))

    if score is None:
        raise PronunciationAssessmentUnavailable(
            "Azure Speech não retornou pontuação de pronúncia para este áudio."
        )

    feedback_title, feedback_detail = _build_feedback(score, word_scores)

    return {
        "transcribed_text": transcribed_text,
        "score": score,
        "word_scores": word_scores,
        "feedback_title": feedback_title,
        "feedback_detail": feedback_detail,
        "accuracy_score": _clamp_score(pron.get("AccuracyScore")),
        "fluency_score": _clamp_score(pron.get("FluencyScore")),
        "completeness_score": _clamp_score(pron.get("CompletenessScore")),
        "prosody_score": _clamp_score(pron.get("ProsodyScore")),
    }


def _azure_transcribe_wav(wav_path: str, locale: str) -> str:
    region = _azure_speech_region()
    key = _azure_speech_key()
    if not region or not key:
        raise PronunciationAssessmentUnavailable(
            "Azure Speech não configurado. Defina LIT_SPEECH_API e LIT_SPEECH_REGION."
        )

    with open(wav_path, "rb") as audio_file:
        wav_bytes = audio_file.read()

    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    response = requests.post(
        url,
        params={"language": locale, "format": "simple"},
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        },
        data=wav_bytes,
        timeout=45,
    )
    if not response.ok:
        raise RuntimeError(f"Azure Speech STT erro {response.status_code}: {response.text[:300]}")

    data = response.json()
    if data.get("RecognitionStatus") != "Success":
        raise RuntimeError(f"Azure Speech STT falhou: {data.get('RecognitionStatus')}")

    return (data.get("DisplayText") or "").strip()


def _azure_assess_wav(wav_path: str, locale: str, reference_text: str) -> dict[str, Any]:
    """
    Azure Pronunciation Assessment via REST (Comprehensive + Phoneme + Miscue).
    """
    region = _azure_speech_region()
    key = _azure_speech_key()
    if not region or not key:
        raise PronunciationAssessmentUnavailable(
            "Azure Speech não configurado. Defina LIT_SPEECH_API e LIT_SPEECH_REGION."
        )

    assessment_header = base64.b64encode(json.dumps({
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableMiscue": True,
    }).encode("utf-8")).decode("ascii")

    with open(wav_path, "rb") as audio_file:
        wav_bytes = audio_file.read()

    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    response = requests.post(
        url,
        params={"language": locale, "format": "detailed"},
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Pronunciation-Assessment": assessment_header,
        },
        data=wav_bytes,
        timeout=45,
    )
    if not response.ok:
        raise RuntimeError(
            f"Azure Pronunciation Assessment erro {response.status_code}: {response.text[:300]}"
        )

    data = response.json()
    status = data.get("RecognitionStatus")
    if status != "Success":
        raise RuntimeError(f"Azure Pronunciation Assessment falhou: {status}")

    return _parse_azure_assessment_json(data, reference_text)


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
    """Áudio → texto. Azure STT quando configurado; Whisper só como fallback."""
    locale = _resolve_locale(language)
    if _azure_available():
        tmp_path, wav_path = _prepare_audio_paths(audio_bytes)
        try:
            return _azure_transcribe_wav(wav_path, locale)
        except Exception as exc:
            logger.exception("Falha no Azure Speech STT, usando Whisper: %s", exc)
        finally:
            _cleanup_paths(tmp_path, wav_path if wav_path != tmp_path else None)
    elif _azure_speech_key() and not _azure_speech_region():
        logger.warning("LIT_SPEECH_API definida, mas LIT_SPEECH_REGION ausente — usando Whisper.")

    return _transcribe_whisper(audio_bytes, language)


def assess_pronunciation(
    audio_bytes: bytes,
    language: str,
    reference_text: str,
) -> dict[str, Any]:
    """
    Avaliação de pronúncia exclusivamente via Azure Pronunciation Assessment.
    Retorna score real (PronScore), word_scores e feedback natural.
    """
    reference = (reference_text or "").strip()
    if not reference:
        raise PronunciationAssessmentUnavailable("Texto de referência vazio.")

    if not _azure_available():
        missing = []
        if not _azure_speech_key():
            missing.append("LIT_SPEECH_API")
        if not _azure_speech_region():
            missing.append("LIT_SPEECH_REGION")
        raise PronunciationAssessmentUnavailable(
            f"Azure Speech não configurado ({', '.join(missing)})."
        )

    locale = _resolve_locale(language)
    tmp_path, wav_path = _prepare_audio_paths(audio_bytes)
    try:
        return _azure_assess_wav(wav_path, locale, reference)
    except PronunciationAssessmentUnavailable:
        raise
    except Exception as exc:
        logger.exception("Falha na avaliação de pronúncia Azure: %s", exc)
        raise PronunciationAssessmentUnavailable(
            "Não foi possível avaliar a pronúncia com a Azure Speech. Tente novamente."
        ) from exc
    finally:
        _cleanup_paths(tmp_path, wav_path if wav_path != tmp_path else None)
