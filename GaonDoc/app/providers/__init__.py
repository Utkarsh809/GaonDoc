from .base import Providers, ProviderError
from .http_provider import HttpLLM, HttpSTT, HttpTTS
from .mock import MockSTT, MockTTS


def build_providers(settings):
    if settings.provider_mode == "mock":
        return Providers(stt=MockSTT(), tts=MockTTS(), llm=None)
    if settings.provider_mode != "http":
        raise ValueError("PROVIDER_MODE must be 'mock' or 'http'")
    stt = HttpSTT(settings) if settings.stt_url else MockSTT()
    tts = HttpTTS(settings) if settings.tts_url else MockTTS()
    llm = HttpLLM(settings) if settings.llm_url else None
    return Providers(stt=stt, tts=tts, llm=llm)


__all__ = ["Providers", "ProviderError", "build_providers"]
