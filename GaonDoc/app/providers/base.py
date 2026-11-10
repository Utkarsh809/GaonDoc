from dataclasses import dataclass
from typing import Optional, Protocol


class ProviderError(RuntimeError):
    pass


@dataclass
class Transcript:
    text: str
    language: str
    confidence: Optional[float] = None


@dataclass
class Speech:
    audio: bytes
    mime: str


class STT(Protocol):
    async def transcribe(
        self, audio: bytes, language: str, filename: str = "audio.webm", content_type: str = "audio/webm"
    ) -> Transcript: ...


class TTS(Protocol):
    async def synthesize(self, text: str, language: str) -> Speech: ...


class LLM(Protocol):
    async def complete(self, system: str, user: str) -> str: ...


@dataclass
class Providers:
    stt: STT
    tts: TTS
    llm: Optional[LLM]
