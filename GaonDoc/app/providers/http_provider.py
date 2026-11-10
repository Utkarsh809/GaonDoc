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

    async def transcribe(self, audio, language, filename="audio.wav", content_type="audio/wav"):
        import asyncio
        s = self.s
        data = {s.stt_lang_field: s.stt_lang_map.get(language, language), **s.stt_extra}
        headers = auth_headers(s.stt_key, s.stt_auth_header, s.stt_auth_scheme)
        response = None
        last_exc = None

        for attempt in range(3):
            files = {s.stt_file_field: (filename, audio, content_type)}
            try:
                async with httpx.AsyncClient(timeout=45, transport=self.transport) as client:
                    response = await client.post(s.stt_url, headers=headers, data=data, files=files)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue
                raise ProviderError("stt unreachable") from exc
            except httpx.HTTPError as exc:
                raise ProviderError("stt unreachable") from exc

            # Retry transient upstream/gateway errors (502, 503, 504)
            if response.status_code in (502, 503, 504) and attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            break

        if response is None:
            raise ProviderError("stt unreachable") from last_exc

        if response.status_code >= 400:
            err_msg = ""
            try:
                err_msg = response.json().get("error", {}).get("message", "")
            except Exception:
                pass
            detail = f" ({err_msg})" if err_msg else ""
            raise ProviderError(f"stt http {response.status_code}{detail}")
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
        headers = auth_headers(s.llm_key, s.llm_auth_header, s.llm_auth_scheme)

        models = [s.llm_model]
        if "googleapis.com" in s.llm_url:
            for alt in ("gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash"):
                if alt not in models:
                    models.append(alt)

        response = None
        for model_name in models:
            payload = {
                "model": model_name,
                "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            }
            try:
                async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
                    response = await client.post(s.llm_url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                if model_name != models[-1]:
                    continue
                raise ProviderError("llm unreachable") from exc

            # If quota exceeded or model deprecated, try next model in chain
            if response.status_code in (429, 404) and model_name != models[-1]:
                continue
            break

        if response is None:
            raise ProviderError("llm unreachable")
        if response.status_code >= 400:
            raise ProviderError(f"llm http {response.status_code}")
        try:
            return str(dig(response.json(), s.llm_text_path)).strip()
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("llm response shape") from exc
