import base64
import json

import httpx
import pytest

from app.config import Settings
from app.pipeline.translate import translate
from app.providers import ProviderError
from app.providers.http_provider import HttpLLM, HttpSTT, HttpTTS, dig


def run(coro):
    import asyncio

    return asyncio.run(coro)


def test_dig_handles_lists_and_dicts():
    assert dig({"a": [{"b": "x"}]}, "a.0.b") == "x"


def test_stt_maps_fields_and_parses_response():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.content
        return httpx.Response(200, json={"result": {"text": " bukhar hai ", "conf": 0.91}})

    settings = Settings(
        stt_url="http://stt.test/v1", stt_key="k", stt_text_path="result.text", stt_conf_path="result.conf",
        stt_lang_map={"hi": "hi-IN"}, stt_extra={"model": "m1"}, stt_file_field="audio",
    )
    stt = HttpSTT(settings, transport=httpx.MockTransport(handler))
    transcript = run(stt.transcribe(b"bytes", "hi"))
    assert transcript.text == "bukhar hai"
    assert transcript.confidence == pytest.approx(0.91)
    assert seen["auth"] == "Bearer k"
    assert b"hi-IN" in seen["body"] and b'name="audio"' in seen["body"] and b"m1" in seen["body"]


def test_stt_http_error_becomes_provider_error():
    stt = HttpSTT(Settings(stt_url="http://stt.test"), transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    with pytest.raises(ProviderError):
        run(stt.transcribe(b"x", "hi"))


def test_stt_bad_shape_becomes_provider_error():
    stt = HttpSTT(Settings(stt_url="http://stt.test"), transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"nope": 1})))
    with pytest.raises(ProviderError):
        run(stt.transcribe(b"x", "hi"))


def test_tts_binary_and_base64_modes():
    binary = HttpTTS(Settings(tts_url="http://tts.test"), transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"AUDIO", headers={"content-type": "audio/mpeg"})))
    assert run(binary.synthesize("namaste", "hi")).audio == b"AUDIO"

    def handler(request):
        payload = json.loads(request.content)
        assert payload["input"] == "namaste" and payload["lang"] == "hi-IN" and payload["voice"] == "v1"
        return httpx.Response(200, json={"data": {"audio": base64.b64encode(b"WAV").decode()}})

    settings = Settings(tts_url="http://tts.test", tts_response="json_base64", tts_audio_path="data.audio", tts_text_field="input", tts_lang_field="lang", tts_voice_field="voice", tts_voice="v1", tts_lang_map={"hi": "hi-IN"}, tts_mime="audio/wav")
    speech = run(HttpTTS(settings, transport=httpx.MockTransport(handler)).synthesize("namaste", "hi"))
    assert speech.audio == b"WAV" and speech.mime == "audio/wav"


def test_llm_translation_carries_glossary_and_falls_back():
    captured = {}

    def handler(request):
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "I have had fever for three days"}}]})

    llm = HttpLLM(Settings(llm_url="http://llm.test", llm_model="m"), transport=httpx.MockTransport(handler))
    text, mode = run(translate(llm, "teen din se bukhar", "hi", "en", "bukhar = Fever"))
    assert (text, mode) == ("I have had fever for three days", "llm")
    assert "bukhar = Fever" in captured["payload"]["messages"][0]["content"]
    assert captured["payload"]["temperature"] == 0

    broken = HttpLLM(Settings(llm_url="http://llm.test"), transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert run(translate(broken, "teen din se bukhar", "hi", "en")) == ("teen din se bukhar", "passthrough")
