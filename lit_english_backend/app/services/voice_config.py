"""
Configuração do módulo de Conversa com IA Tutor (Azure Voice Live + phi4-mm-realtime).

Variáveis de ambiente esperadas:
- AZURE_SPEECH_KEY            -> chave do recurso Azure (Speech / AI Foundry multi-serviço)
- AZURE_SPEECH_REGION         -> região do recurso (ex: "eastus2")
- AZURE_VOICELIVE_MODEL       -> "phi4-mm-realtime" (esse é o default se a variável não for definida)

Opcionais (só defina se o seu recurso usar um endpoint customizado, tipo
"https://minha-lit.cognitiveservices.azure.com/" ou "...services.ai.azure.com/"):
- AZURE_VOICELIVE_ENDPOINT
- AZURE_VOICELIVE_API_VERSION (default abaixo)

Se AZURE_VOICELIVE_ENDPOINT não for definida, o endpoint é montado a partir da região
(padrão regional do recurso Cognitive Services). Se o seu recurso for "custom domain"
(Foundry), defina AZURE_VOICELIVE_ENDPOINT explicitamente -- é o caminho mais confiável.

IMPORTANTE: este módulo NÃO levanta exceção na importação, mesmo se as
credenciais não estiverem configuradas. Isso evita que a API inteira (todos
os outros módulos: flashcards, exercícios, etc.) fique fora do ar só porque
a Conversa com IA Tutor ainda não tem as variáveis do Azure configuradas no
Railway. A validação só acontece quando alguém de fato tenta abrir uma sessão
de conversa (ver `is_configured()` e o uso em conversation_session_manager.py
e no router).
"""

import os


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


AZURE_SPEECH_KEY = _clean(os.getenv("AZURE_SPEECH_KEY"))
AZURE_SPEECH_REGION = _clean(os.getenv("AZURE_SPEECH_REGION"))
VOICELIVE_MODEL = _clean(os.getenv("AZURE_VOICELIVE_MODEL")) or "phi4-mm-realtime"
VOICELIVE_API_VERSION = _clean(os.getenv("AZURE_VOICELIVE_API_VERSION")) or "2025-10-01"

_explicit_endpoint = _clean(os.getenv("AZURE_VOICELIVE_ENDPOINT"))

_config_error: str | None = None

if not AZURE_SPEECH_KEY:
    _config_error = "AZURE_SPEECH_KEY não configurada."
elif _explicit_endpoint:
    _host = _explicit_endpoint.replace("https://", "").replace("wss://", "").rstrip("/")
elif AZURE_SPEECH_REGION:
    _host = f"{AZURE_SPEECH_REGION}.cognitiveservices.azure.com"
else:
    _config_error = "Defina AZURE_SPEECH_REGION ou AZURE_VOICELIVE_ENDPOINT."

if _config_error:
    _host = None

VOICELIVE_WS_BASE = f"wss://{_host}/voice-live/realtime" if _host else None
VOICELIVE_API_KEY = AZURE_SPEECH_KEY

# TTS "clássico" (usado no endpoint /conversation/tts, fora da sessão em tempo real,
# para o botão "Ouvir" de cada bolha de mensagem)
TTS_REST_URL = (
    f"https://{AZURE_SPEECH_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    if AZURE_SPEECH_REGION
    else None
)

# Timeout de inatividade da sessão de conversa
SESSION_TIMEOUT_MINUTES = int(os.getenv("LIT_CONVERSATION_TIMEOUT_MINUTES", "30"))

# Voz padrão do tutor (pt/en neutra, ajuste à vontade)
DEFAULT_TUTOR_VOICE = os.getenv("LIT_TUTOR_VOICE", "en-US-AvaMultilingualNeural")


def is_configured() -> bool:
    """True se as credenciais mínimas do Azure Voice Live estão presentes."""
    return _config_error is None


def require_configured() -> None:
    """Levanta RuntimeError com uma mensagem clara se as credenciais faltarem.

    Chame isso só no momento de realmente usar o serviço (abrir sessão de
    voz, chamar TTS), nunca na importação do módulo.
    """
    if _config_error:
        raise RuntimeError(
            f"Conversa com IA Tutor não está configurada: {_config_error} "
            "Defina AZURE_SPEECH_KEY e AZURE_SPEECH_REGION (ou AZURE_VOICELIVE_ENDPOINT) "
            "nas variáveis de ambiente do backend."
        )
