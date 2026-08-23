from __future__ import annotations

from pydantic import BaseModel


class TranslateRequest(BaseModel):
    text: str


class TranslateResponse(BaseModel):
    original: str
    translated: str


class TTSRequest(BaseModel):
    text: str
    lang: str = "en-US"  # "en-US" ou "pt-BR"


class SpeechErrorItem(BaseModel):
    wrong_fragment: str
    correct_fragment: str
    explanation_pt_br: str


class SpeechAnalysis(BaseModel):
    student_transcript: str
    errors: list[SpeechErrorItem] = []
    corrected_sentence: str
    feedback_pt_br: str
