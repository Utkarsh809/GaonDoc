import io
import wave

from .base import Speech, Transcript


class MockSTT:
    async def transcribe(self, audio, language, filename="audio.webm", content_type="audio/webm"):
        try:
            text = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            text = ""
        return Transcript(text=text, language=language, confidence=1.0 if text else 0.0)


class MockTTS:
    async def synthesize(self, text, language):
        seconds = min(10.0, max(0.6, len(text) * 0.04))
        rate = 8000
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(b"\x00\x00" * int(rate * seconds))
        return Speech(audio=buffer.getvalue(), mime="audio/wav")
