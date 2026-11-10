import json
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def _json(name):
    raw = os.getenv(name, "").strip()
    return json.loads(raw) if raw else {}


@dataclass(frozen=True)
class Settings:
    provider_mode: str = "mock"
    stt_url: str = ""
    stt_key: str = ""
    stt_auth_header: str = "Authorization"
    stt_auth_scheme: str = "Bearer"
    stt_file_field: str = "file"
    stt_lang_field: str = "language"
    stt_text_path: str = "text"
    stt_conf_path: str = ""
    stt_extra: dict = field(default_factory=dict)
    stt_lang_map: dict = field(default_factory=dict)
    tts_url: str = ""
    tts_key: str = ""
    tts_auth_header: str = "Authorization"
    tts_auth_scheme: str = "Bearer"
    tts_text_field: str = "text"
    tts_lang_field: str = "language"
    tts_voice_field: str = ""
    tts_voice: str = ""
    tts_extra: dict = field(default_factory=dict)
    tts_lang_map: dict = field(default_factory=dict)
    tts_response: str = "audio"
    tts_audio_path: str = "audio"
    tts_mime: str = "audio/mpeg"
    llm_url: str = ""
    llm_key: str = ""
    llm_model: str = ""
    llm_auth_header: str = "Authorization"
    llm_auth_scheme: str = "Bearer"
    llm_text_path: str = "choices.0.message.content"
    session_ttl_seconds: int = 1800
    max_audio_bytes: int = 10 * 1024 * 1024
    allowed_origins: tuple = ("*",)
    reminder_times: dict = field(
        default_factory=lambda: {
            "morning": "08:00",
            "afternoon": "14:00",
            "evening": "18:00",
            "night": "21:00",
        }
    )


def load_settings():
    env = os.getenv
    return Settings(
        provider_mode=env("PROVIDER_MODE", "mock").strip().lower(),
        stt_url=env("STT_URL", ""),
        stt_key=env("STT_KEY", ""),
        stt_auth_header=env("STT_AUTH_HEADER", "Authorization"),
        stt_auth_scheme=env("STT_AUTH_SCHEME", "Bearer"),
        stt_file_field=env("STT_FILE_FIELD", "file"),
        stt_lang_field=env("STT_LANG_FIELD", "language"),
        stt_text_path=env("STT_TEXT_PATH", "text"),
        stt_conf_path=env("STT_CONF_PATH", ""),
        stt_extra=_json("STT_EXTRA"),
        stt_lang_map=_json("STT_LANG_MAP"),
        tts_url=env("TTS_URL", ""),
        tts_key=env("TTS_KEY", ""),
        tts_auth_header=env("TTS_AUTH_HEADER", "Authorization"),
        tts_auth_scheme=env("TTS_AUTH_SCHEME", "Bearer"),
        tts_text_field=env("TTS_TEXT_FIELD", "text"),
        tts_lang_field=env("TTS_LANG_FIELD", "language"),
        tts_voice_field=env("TTS_VOICE_FIELD", ""),
        tts_voice=env("TTS_VOICE", ""),
        tts_extra=_json("TTS_EXTRA"),
        tts_lang_map=_json("TTS_LANG_MAP"),
        tts_response=env("TTS_RESPONSE", "audio"),
        tts_audio_path=env("TTS_AUDIO_PATH", "audio"),
        tts_mime=env("TTS_MIME", "audio/mpeg"),
        llm_url=env("LLM_URL", ""),
        llm_key=env("LLM_KEY", ""),
        llm_model=env("LLM_MODEL", ""),
        llm_auth_header=env("LLM_AUTH_HEADER", "Authorization"),
        llm_auth_scheme=env("LLM_AUTH_SCHEME", "Bearer"),
        llm_text_path=env("LLM_TEXT_PATH", "choices.0.message.content"),
        session_ttl_seconds=int(env("SESSION_TTL_SECONDS", "1800")),
        max_audio_bytes=int(env("MAX_AUDIO_BYTES", str(10 * 1024 * 1024))),
        allowed_origins=tuple(o.strip() for o in env("ALLOWED_ORIGINS", "*").split(",") if o.strip()),
    )
