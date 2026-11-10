import base64

import httpx

from .base import ProviderError, Speech, Transcript


def dig(data, path):
    current = data
    for part in path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def auth_headers(key, header, scheme):
    if not key:
        return {}
    return {header: f"{scheme} {key}".strip() if scheme else key}


class HttpSTT:
    def __init__(self, settings, transport=None):
        self.s = settings
        self.transport = transport

    async def transcribe(self, audio, language, filename="audio.webm", content_type="audio/webm"):
        s = self.s
        data = {s.stt_lang_field: s.stt_lang_map.get(language, language), **s.stt_extra}
        files = {s.stt_file_field: (filename, audio, content_type)}
        headers = auth_headers(s.stt_key, s.stt_auth_header, s.stt_auth_scheme)
        try:
            async with httpx.AsyncClient(timeout=90, transport=self.transport) as client:
                response = await client.post(s.stt_url, headers=headers, data=data, files=files)
        except httpx.HTTPError as exc:
            raise ProviderError("stt unreachable") from exc
        if response.status_code >= 400:
            raise ProviderError(f"stt http {response.status_code}")
        try:
            body = response.json()
            text = dig(body, s.stt_text_path)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("stt response shape") from exc
        confidence = None
        if s.stt_conf_path:
            try:
                confidence = float(dig(body, s.stt_conf_path))
            except (KeyError, IndexError, TypeError, ValueError):
                confidence = None
        return Transcript(text=str(text).strip(), language=language, confidence=confidence)


class HttpTTS:
    def __init__(self, settings, transport=None):
        self.s = settings
        self.transport = transport

    async def synthesize(self, text, language):
        s = self.s
        payload = {s.tts_text_field: text, s.tts_lang_field: s.tts_lang_map.get(language, language), **s.tts_extra}
        if s.tts_voice_field and s.tts_voice:
            payload[s.tts_voice_field] = s.tts_voice
        headers = auth_headers(s.tts_key, s.tts_auth_header, s.tts_auth_scheme)
        try:
            async with httpx.AsyncClient(timeout=90, transport=self.transport) as client:
                response = await client.post(s.tts_url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError("tts unreachable") from exc
        if response.status_code >= 400:
            raise ProviderError(f"tts http {response.status_code}")
        if s.tts_response == "json_base64":
            try:
                audio = base64.b64decode(dig(response.json(), s.tts_audio_path))
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise ProviderError("tts response shape") from exc
            return Speech(audio=audio, mime=s.tts_mime)
        mime = response.headers.get("content-type", s.tts_mime).split(";")[0]
        if mime in ("application/octet-stream", "binary/octet-stream", ""):
            mime = s.tts_mime
        return Speech(audio=response.content, mime=mime)


class HttpLLM:
    def __init__(self, settings, transport=None):
        self.s = settings
        self.transport = transport

    async def complete(self, system, user):
        s = self.s
        payload = {
            "model": s.llm_model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        headers = auth_headers(s.llm_key, s.llm_auth_header, s.llm_auth_scheme)
        try:
            async with httpx.AsyncClient(timeout=90, transport=self.transport) as client:
                response = await client.post(s.llm_url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError("llm unreachable") from exc
        if response.status_code >= 400:
            raise ProviderError(f"llm http {response.status_code}")
        try:
            return str(dig(response.json(), s.llm_text_path)).strip()
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("llm response shape") from exc
