"""
Motor de transcrição e avaliação de pronúncia — LIT English

Variáveis de ambiente (Azure Speech):
  LIT_SPEECH_API    → chave (subscription key)
  LIT_SPEECH_REGION → região (ex.: brazilsouth, eastus)

`assess_pronunciation()` usa Azure Pronunciation Assessment (SDK + REST fallback).
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
    for env_key in ("LIT_SPEECH_API", "AZURE_SPEECH_KEY", "AZURE_SPEECH_API_KEY"):
        key = (os.environ.get(env_key) or "").strip()
        if key and not key.startswith("http"):
            return key
    return None


def _normalize_region(raw: str) -> str:
    region = (raw or "").strip()
    if not region:
        return region

    lowered = region.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        match = re.match(r"https?://([^./]+)", lowered)
        if match:
            return match.group(1)

    # Usuário colou "Brazil South" ou "East US"
    compact = re.sub(r"[^a-z0-9]", "", region.lower())
    aliases = {
        "brazilsouth": "brazilsouth",
        "eastus": "eastus",
        "eastus2": "eastus2",
        "westus": "westus",
        "westeurope": "westeurope",
        "northeurope": "northeurope",
    }
    return aliases.get(compact, compact)


def _azure_speech_region() -> str | None:
    for env_key in ("LIT_SPEECH_REGION", "AZURE_SPEECH_REGION", "SPEECH_REGION"):
        raw = (os.environ.get(env_key) or "").strip()
        if raw:
            return _normalize_region(raw)
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
        if result.returncode != 0:
            logger.warning(
                "ffmpeg falhou (code=%s): %s",
                result.returncode,
                (result.stderr or b"").decode("utf-8", errors="replace")[:400],
            )
            return input_path
        return output_path if os.path.exists(output_path) else input_path
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("ffmpeg indisponível ou erro na conversão: %s", exc)
        return input_path


def _prepare_wav_bytes(audio_bytes: bytes) -> tuple[bytes, str, list[str]]:
    """Converte o áudio recebido do navegador para WAV PCM 16 kHz mono."""
    suffix = ".webm"
    if audio_bytes[:4] == b"OggS":
        suffix = ".ogg"
    elif audio_bytes[:4] == b"RIFF":
        suffix = ".wav"

    cleanup: list[str] = []
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    cleanup.append(tmp_path)

    wav_path = convert_audio_to_wav(tmp_path)
    if wav_path != tmp_path:
        cleanup.append(wav_path)

    with open(wav_path, "rb") as wav_file:
        wav_bytes = wav_file.read()

    if wav_bytes[:4] != b"RIFF":
        _cleanup_paths(*cleanup)
        raise PronunciationAssessmentUnavailable(
            "Não foi possível converter o áudio para WAV. "
            "Verifique se o ffmpeg está instalado no servidor."
        )

    return wav_bytes, wav_path, cleanup


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
    status = data.get("RecognitionStatus")
    if status and status != "Success":
        messages = {
            "InitialSilenceTimeout": "Não detectamos sua voz. Fale assim que a gravação começar.",
            "NoMatch": "Não conseguimos entender o áudio. Tente falar mais alto e claro.",
            "BabbleTimeout": "Áudio confuso ou com muito ruído. Tente novamente em um lugar silencioso.",
        }
        raise PronunciationAssessmentUnavailable(
            messages.get(status, f"Azure retornou status: {status}")
        )

    nbest = (data.get("NBest") or [{}])[0]
    pron = nbest.get("PronunciationAssessment") or data.get("PronunciationAssessment") or {}

    transcribed_text = (
        nbest.get("Display")
        or nbest.get("Lexical")
        or nbest.get("ITN")
        or nbest.get("MaskedITN")
        or data.get("DisplayText")
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
        logger.warning("Resposta Azure sem pontuação. Keys=%s", list(data.keys()))
        raise PronunciationAssessmentUnavailable(
            "Azure não retornou pontuação de pronúncia. "
            "Confirme se o recurso Speech suporta Pronunciation Assessment nesta região/idioma."
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


def _build_pronunciation_header(reference_text: str) -> str:
    # Azure espera strings "True"/"False" nos flags booleanos (documentação oficial).
    params = {
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableMiscue": "True",
        "EnableProsodyAssessment": "True",
    }
    return base64.b64encode(json.dumps(params, ensure_ascii=False).encode("utf-8")).decode("ascii")


def _azure_http_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error") or {}
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if payload.get("Message"):
                return str(payload["Message"])
    except Exception:
        pass
    text = (response.text or "").strip()
    return text[:240] if text else f"HTTP {response.status_code}"


def _assess_with_rest(wav_bytes: bytes, locale: str, reference_text: str) -> dict[str, Any]:
    region = _azure_speech_region()
    key = _azure_speech_key()
    if not region or not key:
        raise PronunciationAssessmentUnavailable(
            "Azure Speech não configurado. Defina LIT_SPEECH_API e LIT_SPEECH_REGION."
        )

    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    response = requests.post(
        url,
        params={"language": locale, "format": "detailed"},
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Accept": "application/json",
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Pronunciation-Assessment": _build_pronunciation_header(reference_text),
        },
        data=wav_bytes,
        timeout=45,
    )
    if not response.ok:
        detail = _azure_http_error_detail(response)
        raise PronunciationAssessmentUnavailable(
            f"Azure Speech recusou a requisição ({response.status_code}): {detail}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise PronunciationAssessmentUnavailable(
            "Azure Speech retornou resposta inválida."
        ) from exc

    return _parse_azure_assessment_json(data, reference_text)


def _assess_with_sdk(wav_path: str, locale: str, reference_text: str) -> dict[str, Any]:
    import azure.cognitiveservices.speech as speechsdk

    region = _azure_speech_region()
    key = _azure_speech_key()
    if not region or not key:
        raise PronunciationAssessmentUnavailable(
            "Azure Speech não configurado. Defina LIT_SPEECH_API e LIT_SPEECH_REGION."
        )

    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_recognition_language = locale
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceResponse_RequestDetailedResultTrueFalse,
        "true",
    )

    audio_config = speechsdk.audio.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    pronunciation_config.enable_prosody_assessment = True
    pronunciation_config.apply_to(recognizer)

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.NoMatch:
        raise PronunciationAssessmentUnavailable(
            "Não conseguimos entender o áudio. Fale mais alto e claro."
        )
    if result.reason == speechsdk.ResultReason.Canceled:
        cancellation = result.cancellation_details
        detail = cancellation.error_details if cancellation else "cancelado"
        raise PronunciationAssessmentUnavailable(f"Azure cancelou a análise: {detail}")
    if result.reason != speechsdk.ResultReason.RecognizedSpeech:
        raise PronunciationAssessmentUnavailable(
            f"Azure não reconheceu o áudio ({result.reason.name})."
        )

    json_result = result.properties.get(
        speechsdk.PropertyId.SpeechServiceResponse_JsonResult
    )
    if not json_result:
        raise PronunciationAssessmentUnavailable(
            "Azure SDK não retornou JSON detalhado de pronúncia."
        )

    data = json.loads(json_result)
    return _parse_azure_assessment_json(data, reference_text)


def _assess_wav(wav_bytes: bytes, wav_path: str, locale: str, reference_text: str) -> dict[str, Any]:
    errors: list[str] = []

    try:
        return _assess_with_sdk(wav_path, locale, reference_text)
    except PronunciationAssessmentUnavailable as exc:
        errors.append(f"SDK: {exc}")
        logger.warning("Azure SDK falhou, tentando REST: %s", exc)
    except Exception as exc:
        errors.append(f"SDK: {exc}")
        logger.exception("Azure SDK erro inesperado")

    try:
        return _assess_with_rest(wav_bytes, locale, reference_text)
    except PronunciationAssessmentUnavailable:
        raise
    except Exception as exc:
        errors.append(f"REST: {exc}")
        logger.exception("Azure REST erro inesperado")

    raise PronunciationAssessmentUnavailable(
        "Azure Speech falhou nas duas vias (SDK e REST). "
        + " | ".join(errors[:2])
    )


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
    locale = _resolve_locale(language)
    if _azure_available():
        cleanup: list[str] = []
        try:
            wav_bytes, _wav_path, cleanup = _prepare_wav_bytes(audio_bytes)
            region = _azure_speech_region()
            key = _azure_speech_key()
            url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
            response = requests.post(
                url,
                params={"language": locale, "format": "simple"},
                headers={
                    "Ocp-Apim-Subscription-Key": key,
                    "Accept": "application/json",
                    "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
                },
                data=wav_bytes,
                timeout=45,
            )
            if response.ok:
                data = response.json()
                if data.get("RecognitionStatus") == "Success":
                    return (data.get("DisplayText") or "").strip()
        except Exception as exc:
            logger.exception("Falha no Azure Speech STT, usando Whisper: %s", exc)
        finally:
            _cleanup_paths(*cleanup)
    elif _azure_speech_key() and not _azure_speech_region():
        logger.warning("LIT_SPEECH_API definida, mas LIT_SPEECH_REGION ausente — usando Whisper.")

    return _transcribe_whisper(audio_bytes, language)


def assess_pronunciation(
    audio_bytes: bytes,
    language: str,
    reference_text: str,
) -> dict[str, Any]:
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
    cleanup: list[str] = []
    try:
        wav_bytes, wav_path, cleanup = _prepare_wav_bytes(audio_bytes)
        return _assess_wav(wav_bytes, wav_path, locale, reference)
    except PronunciationAssessmentUnavailable:
        raise
    except Exception as exc:
        logger.exception("Falha inesperada na avaliação Azure: %s", exc)
        raise PronunciationAssessmentUnavailable(
            f"Erro ao processar áudio para a Azure: {exc}"
        ) from exc
    finally:
        _cleanup_paths(*cleanup)
