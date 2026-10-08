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
import math
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
    "spanish": "es-ES",
    "german": "de-DE",
    "portuguese": "pt-BR",
    "ingles": "en-US",
    "italiano": "it-IT",
    "frances": "fr-FR",
    "espanhol": "es-ES",
    "alemao": "de-DE",
    "portugues": "pt-BR",
}

# Mapa ISO 639-1 (o que o Whisper devolve na detecção automática) -> nomes
# internos usados no resto do app.
WHISPER_ISO_TO_LANGUAGE = {
    "en": "english",
    "it": "italian",
    "fr": "french",
    "es": "spanish",
    "de": "german",
    "pt": "portuguese",
}


class PronunciationAssessmentUnavailable(Exception):
    """Azure Speech indisponível ou resposta sem pontuação de pronúncia."""


_CREDENTIALS_CACHE: tuple[str, str] | None = None


def _clean_env(value: str) -> str:
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    return value


def _parse_connection_string(raw: str) -> tuple[str | None, str | None]:
    """Aceita string do portal Azure: Endpoint=...;Key=..."""
    if "key=" not in raw.lower():
        return None, None

    key: str | None = None
    region: str | None = None
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip().lower()
        value = _clean_env(value)
        if name == "key" and value:
            key = value
        elif name == "endpoint" and value:
            region = _normalize_region(value)
    return key, region


def _normalize_region(raw: str) -> str:
    region = _clean_env(raw)
    if not region:
        return region

    lowered = region.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        match = re.match(r"https?://([^./]+)", lowered)
        if match:
            return match.group(1)

    compact = re.sub(r"[^a-z0-9]", "", region.lower())
    aliases = {
        "brazilsouth": "brazilsouth",
        "eastus": "eastus",
        "eastus2": "eastus2",
        "westus": "westus",
        "westeurope": "westeurope",
        "northeurope": "northeurope",
        "centralus": "centralus",
        "southcentralus": "southcentralus",
    }
    return aliases.get(compact, compact)


def _get_azure_credentials() -> tuple[str, str]:
    global _CREDENTIALS_CACHE
    if _CREDENTIALS_CACHE:
        return _CREDENTIALS_CACHE

    key: str | None = None
    region: str | None = None

    for env_key in ("LIT_SPEECH_API", "AZURE_SPEECH_KEY", "AZURE_SPEECH_API_KEY"):
        raw = _clean_env(os.environ.get(env_key) or "")
        if not raw:
            continue

        conn_key, conn_region = _parse_connection_string(raw)
        if conn_key:
            key = conn_key
            if conn_region:
                region = conn_region
            break

        if raw.lower().startswith("key="):
            key = raw.split("=", 1)[1].strip()
            break

        if not raw.lower().startswith("http") and len(raw) >= 20:
            key = raw
            break

    if not region:
        for env_key in ("LIT_SPEECH_REGION", "AZURE_SPEECH_REGION", "SPEECH_REGION"):
            raw = _clean_env(os.environ.get(env_key) or "")
            if raw:
                region = _normalize_region(raw)
                break

    if not key or not region:
        missing = []
        if not key:
            missing.append("LIT_SPEECH_API (Key 1 do recurso Speech)")
        if not region:
            missing.append("LIT_SPEECH_REGION (ex.: brazilsouth)")
        raise PronunciationAssessmentUnavailable(
            f"Azure Speech não configurado. Faltando: {', '.join(missing)}."
        )

    _CREDENTIALS_CACHE = (key, region)
    logger.info("Credenciais Azure Speech resolvidas: região=%s (chave de %s caracteres)", region, len(key))
    return _CREDENTIALS_CACHE


def _azure_speech_key() -> str | None:
    try:
        return _get_azure_credentials()[0]
    except PronunciationAssessmentUnavailable:
        return None


def _azure_speech_region() -> str | None:
    try:
        return _get_azure_credentials()[1]
    except PronunciationAssessmentUnavailable:
        return None


def _azure_available() -> bool:
    try:
        _get_azure_credentials()
        return True
    except PronunciationAssessmentUnavailable:
        return False


def _azure_auth_error_message(status_code: int, detail: str, region: str) -> str:
    if status_code != 401:
        return f"Azure Speech recusou a requisição ({status_code}): {detail}"

    return (
        "Autenticação Azure recusada (401). A chave ou a região está incorreta. "
        "No portal Azure, abra seu recurso Speech → Keys and Endpoint: "
        "copie Key 1 para LIT_SPEECH_API e a Location/Region (ex.: brazilsouth) "
        f"para LIT_SPEECH_REGION. Ambos precisam ser do MESMO recurso. "
        f"Região usada agora: {region}."
    )


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
            # Mesma questão do nível NBest: a Azure pode colocar a avaliação
            # da palavra dentro de "PronunciationAssessment" ou direto no
            # próprio objeto da palavra (word_info["AccuracyScore"]).
            assessment = word_info.get("PronunciationAssessment") or {}
            if not assessment:
                assessment = {
                    k: word_info[k]
                    for k in ("AccuracyScore", "ErrorType")
                    if k in word_info
                }
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


def _apply_phoneme_penalty(
    pron_score: int,
    word_scores: list[dict[str, Any]],
    phoneme_scores: list[dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    """Transforma o PronScore da Azure em uma nota pedagógica da LIT.

    O PronScore é mantido como ponto de partida, mas a Azure pode reconhecer
    uma palavra inteira corretamente mesmo quando um ou mais fonemas daquela
    palavra estão claramente errados. Para a interface da LIT, um fonema ruim
    deve afetar a palavra e também a nota final.

    Regras:
    - palavra com fonemas avaliados recebe o menor score entre a avaliação da
      palavra e seus fonemas (assim um /b/ 56 torna a palavra problemática);
    - cada fonema abaixo de 70 gera uma penalização proporcional;
    - não há "strict score": o PronScore continua sendo a base oficial;
      a redução é apenas uma camada pedagógica transparente da LIT.
    """
    by_word: dict[str, list[int]] = {}
    for item in phoneme_scores:
        word = str(item.get("word") or "").strip().lower()
        score = _clamp_score(item.get("score"))
        if word and score is not None:
            by_word.setdefault(word, []).append(score)

    adjusted_words: list[dict[str, Any]] = []
    for item in word_scores:
        word = str(item.get("word") or "")
        base = _clamp_score(item.get("score")) or 0
        phonemes = by_word.get(word.strip().lower(), [])
        if phonemes:
            # A menor nota de fonema é o pior som daquela palavra.
            # Isso faz o destaque visual refletir o problema real detectado.
            effective = min(base, min(phonemes))
        else:
            effective = base
        adjusted_words.append({**item, "score": effective})

    # Penalização somente para fonemas realmente fracos. Dois erros de 56 e 42,
    # por exemplo, retiram 14,7 pontos do PronScore 88 -> aproximadamente 73.
    # Um único erro moderado não derruba a nota inteira.
    penalty = sum(max(0, 70 - int(score)) * 0.35 for score in by_phoneme_scores(phoneme_scores))
    penalty = min(35.0, penalty)
    final_score = max(0, min(100, int(round(pron_score - penalty))))
    return final_score, adjusted_words


def by_phoneme_scores(phoneme_scores: list[dict[str, Any]]) -> list[int]:
    scores: list[int] = []
    for item in phoneme_scores:
        score = _clamp_score(item.get("score"))
        if score is not None:
            scores.append(score)
    return scores


def _extract_phoneme_scores(azure_words: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extrai os scores de fonema retornados pelo Azure.

    O Azure pode devolver os fonemas diretamente em ``Phonemes`` ou dentro de
    ``Syllables[].Phonemes``. Cada fonema traz a nota do fonema esperado e,
    quando disponível, ``NBestPhonemes`` com os sons que o Azure considerou
    como candidatos. Isso permite detectar um som errado mesmo quando a
    palavra inteira foi reconhecida corretamente.
    """
    per_word: list[dict[str, Any]] = []
    flat: list[dict[str, Any]] = []

    for word_info in azure_words:
        word = str(word_info.get("Word") or word_info.get("word") or "").strip()
        phoneme_nodes: list[dict[str, Any]] = []

        direct = word_info.get("Phonemes") or word_info.get("phonemes") or []
        if isinstance(direct, list):
            phoneme_nodes.extend(x for x in direct if isinstance(x, dict))

        syllables = word_info.get("Syllables") or word_info.get("syllables") or []
        if isinstance(syllables, list):
            for syllable in syllables:
                if not isinstance(syllable, dict):
                    continue
                nodes = syllable.get("Phonemes") or syllable.get("phonemes") or []
                if isinstance(nodes, list):
                    phoneme_nodes.extend(x for x in nodes if isinstance(x, dict))

        word_phonemes: list[dict[str, Any]] = []
        for node in phoneme_nodes:
            assessment = node.get("PronunciationAssessment") or {}
            if not assessment and any(k in node for k in ("AccuracyScore", "Score", "NBestPhonemes")):
                assessment = {
                    k: node[k]
                    for k in ("AccuracyScore", "Score", "NBestPhonemes")
                    if k in node
                }

            score = _clamp_score(assessment.get("AccuracyScore", assessment.get("Score")))
            expected = str(node.get("Phoneme") or node.get("phoneme") or "").strip()
            if score is None and not expected:
                continue

            candidates = assessment.get("NBestPhonemes") or node.get("NBestPhonemes") or []
            spoken = None
            if isinstance(candidates, list) and candidates:
                best = candidates[0] if isinstance(candidates[0], dict) else {}
                spoken = str(best.get("Phoneme") or "").strip() or None

            item = {
                "phoneme": expected or None,
                "score": score if score is not None else 0,
                "spoken_phoneme": spoken,
            }
            word_phonemes.append(item)
            flat.append({"word": word, **item})

        if word_phonemes:
            per_word.append({"word": word, "phonemes": word_phonemes})

    return per_word, flat


def _build_feedback(score: int, word_scores: list[dict[str, Any]], phoneme_scores: list[dict[str, Any]]) -> tuple[str, str]:
    weak = sorted(
        [w for w in word_scores if w.get("score", 100) < 80],
        key=lambda item: item.get("score", 0),
    )
    weak_phonemes = sorted(
        [p for p in phoneme_scores if p.get("score", 100) < 75],
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
        title = "Preste atenção à pronúncia"
        if weak_phonemes:
            first = weak_phonemes[0]
            phoneme = first.get("phoneme") or "um som"
            word = first.get("word") or "esta palavra"
            detail = f'O som {phoneme} em "{word}" precisa de mais precisão.'
        elif weak:
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
    pron = nbest.get("PronunciationAssessment") or {}
    if not pron:
        pron = {
            k: nbest[k]
            for k in ("AccuracyScore", "FluencyScore", "CompletenessScore", "PronScore", "ProsodyScore")
            if k in nbest
        }
    if not pron:
        pron = data.get("PronunciationAssessment") or {}

    transcribed_text = (
        nbest.get("Display")
        or nbest.get("Lexical")
        or nbest.get("ITN")
        or nbest.get("MaskedITN")
        or data.get("DisplayText")
        or ""
    ).strip()

    accuracy_score = _clamp_score(pron.get("AccuracyScore"))
    fluency_score = _clamp_score(pron.get("FluencyScore"))
    completeness_score = _clamp_score(pron.get("CompletenessScore"))
    pron_score = _clamp_score(pron.get("PronScore"))
    prosody_score = _clamp_score(pron.get("ProsodyScore"))

    if pron_score is not None:
        azure_score = pron_score
    else:
        component_scores = [s for s in (accuracy_score, fluency_score, completeness_score) if s is not None]
        azure_score = int(round(sum(component_scores) / len(component_scores))) if component_scores else None

    azure_words = nbest.get("Words") or []
    word_scores = _align_word_scores(reference_text, azure_words)
    word_phonemes, phoneme_scores = _extract_phoneme_scores(azure_words)

    if azure_score is None and word_scores:
        scores = [w["score"] for w in word_scores if w.get("score") is not None]
        if scores:
            azure_score = int(round(sum(scores) / len(scores)))

    if azure_score is None:
        logger.warning("Resposta Azure sem pontuação. Keys=%s", list(data.keys()))
        raise PronunciationAssessmentUnavailable(
            "Azure não retornou pontuação de pronúncia. "
            "Confirme se o recurso Speech suporta Pronunciation Assessment nesta região/idioma."
        )

    # O PronScore continua sendo a base oficial do Azure. A LIT só aplica
    # uma penalização pedagógica quando existem fonemas claramente fracos,
    # para que erros reais de som não sejam escondidos por uma nota geral alta.
    base_score = pron_score if pron_score is not None else azure_score
    final_score, word_scores = _apply_phoneme_penalty(
        base_score,
        word_scores,
        phoneme_scores,
    )
    feedback_title, feedback_detail = _build_feedback(
        final_score,
        word_scores,
        phoneme_scores,
    )

    logger.info(
        "Azure PronunciationAssessment: azure_pron=%s lit_score=%s accuracy=%s fluency=%s completeness=%s prosody=%s words=%s phonemes=%s",
        base_score, final_score, accuracy_score, fluency_score, completeness_score,
        prosody_score, len(word_scores), len(phoneme_scores),
    )

    return {
        "transcribed_text": transcribed_text,
        "score": final_score,
        "azure_pron_score": azure_score,
        "word_scores": word_scores,
        "phoneme_scores": word_phonemes,
        "phoneme_issues": [p for p in phoneme_scores if p.get("score", 100) < 75],
        "feedback_title": feedback_title,
        "feedback_detail": feedback_detail,
        "accuracy_score": accuracy_score,
        "fluency_score": fluency_score,
        "completeness_score": completeness_score,
        "pron_score": pron_score,
        "prosody_score": prosody_score,
        "strict_reasons": [],
    }

def _build_pronunciation_header(reference_text: str, locale: str) -> str:
    # Azure espera strings "True"/"False" nos flags booleanos (documentação oficial).
    params = {
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "PhonemeAlphabet": "IPA",
        "Dimension": "Comprehensive",
        "EnableMiscue": "True",
    }
    # Avaliação de prosódia só é suportada em en-US; pedir isso em outros
    # idiomas faz a Azure devolver a avaliação de pronúncia inteira vazia.
    if locale == "en-US":
        params["EnableProsodyAssessment"] = "True"
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
    key, region = _get_azure_credentials()

    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
    response = requests.post(
        url,
        params={"language": locale, "format": "detailed"},
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Accept": "application/json",
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
            "Pronunciation-Assessment": _build_pronunciation_header(reference_text, locale),
        },
        data=wav_bytes,
        timeout=45,
    )
    if not response.ok:
        detail = _azure_http_error_detail(response)
        raise PronunciationAssessmentUnavailable(
            _azure_auth_error_message(response.status_code, detail, region)
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

    key, region = _get_azure_credentials()

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
    # Pedimos IPA para que os problemas de som possam ser mostrados de forma
    # útil ao aluno quando o Azure disponibilizar o nome do fonema.
    try:
        pronunciation_config.phoneme_alphabet = "IPA"
    except Exception:
        # Versões antigas do SDK podem não expor essa propriedade; o REST
        # continua sendo a via principal e já envia PhonemeAlphabet=IPA.
        pass
    # A avaliação de prosódia da Azure só é suportada em en-US. Ativá-la para
    # outros idiomas (italiano, francês, etc.) faz a Azure devolver a
    # avaliação de pronúncia inteira vazia (sem nenhuma nota), silenciosamente
    # -- foi exatamente isso que zerava a pontuação em idiomas != inglês.
    if locale == "en-US":
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
    """Tenta REST primeiro, SDK como plano B.

    Confirmado por log real: o SDK sempre falha nessa hospedagem porque o
    WebSocket (wss://) é bloqueado pela rede de saída
    (WS_OPEN_ERROR_UNDERLYING_IO_OPEN_FAILED); o REST (HTTPS comum) funciona
    normalmente e já devolve a avaliação completa (Accuracy/Fluency/
    Completeness/Words). Usar REST primeiro evita pagar o tempo do SDK
    falhando em toda tentativa antes de cair pro plano B.
    """
    errors: list[str] = []

    try:
        return _assess_with_rest(wav_bytes, locale, reference_text)
    except PronunciationAssessmentUnavailable as exc:
        errors.append(f"REST: {exc}")
        logger.warning("Azure REST falhou, tentando SDK: %s", exc)
    except Exception as exc:
        errors.append(f"REST: {exc}")
        logger.exception("Azure REST erro inesperado")

    try:
        return _assess_with_sdk(wav_path, locale, reference_text)
    except PronunciationAssessmentUnavailable:
        raise
    except Exception as exc:
        errors.append(f"SDK: {exc}")
        logger.exception("Azure SDK erro inesperado")

    raise PronunciationAssessmentUnavailable(
        "Azure Speech falhou nas duas vias (REST e SDK). "
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


def _transcribe_whisper(audio_bytes: bytes, language: str) -> tuple[str, float | None]:
    model = get_whisper_model()
    lang_map = {
        "english": "en", "german": "de", "french": "fr",
        "italian": "it", "spanish": "es", "portuguese": "pt",
    }
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
        segments = list(segments)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        # faster-whisper não devolve uma "confiança" 0-1 diretamente, mas
        # avg_logprob de cada segmento é um bom proxy: quanto mais perto de 0
        # (menos negativo), mais o modelo "acreditou" no que reconheceu nessa
        # língua. Convertendo com exp() cai numa faixa comparável a 0-1, o que
        # permite comparar a passada em inglês com a passada em português.
        confidence: float | None = None
        logprobs = [seg.avg_logprob for seg in segments if seg.avg_logprob is not None]
        if logprobs:
            avg_logprob = sum(logprobs) / len(logprobs)
            confidence = math.exp(avg_logprob)
        return text, confidence
    finally:
        _cleanup_paths(tmp_path, wav_path if wav_path != tmp_path else None)


def transcribe_with_confidence(audio_bytes: bytes, language: str, with_provider: bool = False):
    """Transcreve e devolve também uma confiança 0-1 (quando disponível).

    A confiança é o sinal que permite decidir, sem depender de regex, se uma
    transcrição feita com o reconhecedor de uma língua específica realmente
    corresponde ao que foi falado -- essencial para notar que o aluno falou
    inteiramente na língua nativa mesmo sem usar uma fórmula tipo "como se
    diz".
    """
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
                # "detailed" (em vez de "simple") é o que faz a Azure devolver
                # NBest[0].Confidence -- sem isso não temos como comparar as
                # duas passadas (língua-alvo x língua nativa).
                params={"language": locale, "format": "detailed"},
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
                    nbest = (data.get("NBest") or [{}])[0]
                    text = (
                        nbest.get("Display")
                        or nbest.get("Lexical")
                        or data.get("DisplayText")
                        or ""
                    ).strip()
                    confidence = nbest.get("Confidence")
                    return (text, (float(confidence) if confidence is not None else None), "azure") if with_provider else (text, (float(confidence) if confidence is not None else None))
                if data.get("RecognitionStatus") == "NoMatch":
                    # Reconhecedor dessa língua não achou nada plausível --
                    # sinal forte de que o áudio não está nessa língua.
                    return ("", 0.0, "azure") if with_provider else ("", 0.0)
        except Exception as exc:
            logger.exception("Falha no Azure Speech STT, usando Whisper: %s", exc)
        finally:
            _cleanup_paths(*cleanup)
    elif _azure_speech_key() and not _azure_speech_region():
        logger.warning("LIT_SPEECH_API definida, mas LIT_SPEECH_REGION ausente — usando Whisper.")

    whisper_result = _transcribe_whisper(audio_bytes, language)
    return (whisper_result[0], whisper_result[1], "whisper") if with_provider else whisper_result


def detect_spoken_language(audio_bytes: bytes) -> tuple[str | None, float]:
    """Identifica automaticamente em que língua o áudio foi falado.

    Isso é o que faltava pra ser "automático de verdade" (como o realtime da
    OpenAI): em vez de comparar confiança entre duas transcrições forçadas
    numa língua fixa, deixamos o Whisper fazer o que ele já faz nativamente
    -- detecção de idioma -- sem passar `language=`. O Whisper roda essa
    detecção sobre os primeiros segundos de áudio ANTES de decodificar
    qualquer texto, então isso é rápido (não é uma transcrição completa).

    Devolve (nome_interno_do_idioma, probabilidade) -- ex: ("portuguese",
    0.94). Se o idioma detectado não for um dos que o app conhece, ou o
    Whisper não estiver disponível, devolve (None, 0.0).
    """
    try:
        model = get_whisper_model()
    except Exception:
        logger.warning("Whisper indisponível para detecção automática de idioma", exc_info=True)
        return None, 0.0

    tmp_path, wav_path = _prepare_audio_paths(audio_bytes)
    try:
        # language=None é o que ativa a detecção automática do Whisper.
        # Não iteramos `segments` (é um generator lazy) -- só queremos o
        # `info`, que já vem pronto, então isso não paga o custo de
        # transcrever o áudio inteiro.
        _segments, info = model.transcribe(
            wav_path,
            language=None,
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        iso_code = getattr(info, "language", None)
        probability = float(getattr(info, "language_probability", 0.0) or 0.0)
        detected = WHISPER_ISO_TO_LANGUAGE.get(iso_code) if iso_code else None
        return detected, probability
    except Exception:
        logger.warning("Falha na detecção automática de idioma", exc_info=True)
        return None, 0.0
    finally:
        _cleanup_paths(tmp_path, wav_path if wav_path != tmp_path else None)


def transcribe(audio_bytes: bytes, language: str) -> str:
    text, _confidence = transcribe_with_confidence(audio_bytes, language)
    return text


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
