from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import load_settings
from .pipeline.consult import build_summary, process_prescription, process_turn
from .pipeline.medication import resolve
from .providers import ProviderError, build_providers
from .schemas import PrescriptionRequest, ResolveRequest, SessionCreate
from .session import SessionStore

STATIC = Path(__file__).resolve().parent / "static"
LANGUAGES = ["hi", "en", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "ur", "or"]


def create_app(settings=None, providers=None):
    settings = settings or load_settings()
    providers = providers or build_providers(settings)
    store = SessionStore(settings.session_ttl_seconds)
    app = FastAPI(title="GaonDoc", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def session_or_404(sid):
        try:
            return store.get(sid)
        except KeyError:
            raise HTTPException(404, "session not found or expired")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "provider_mode": settings.provider_mode, "llm_configured": providers.llm is not None, "languages": LANGUAGES}

    @app.post("/api/sessions", status_code=201)
    async def create_session(body: SessionCreate):
        if not body.consent:
            raise HTTPException(422, "patient consent is required")
        try:
            session = store.create(body.patient_language, body.doctor_language)
        except OverflowError:
            raise HTTPException(503, "server is busy")
        return {"id": session.id, "patient_language": session.patient_language, "doctor_language": session.doctor_language}

    @app.delete("/api/sessions/{sid}", status_code=204)
    async def delete_session(sid: str):
        store.delete(sid)

    @app.post("/api/sessions/{sid}/turn")
    async def turn(
        sid: str,
        speaker: Literal["patient", "doctor"] = Form(...),
        text: Optional[str] = Form(None),
        speak: bool = Form(False),
        audio: Optional[UploadFile] = File(None),
    ):
        session = session_or_404(sid)
        language = session.patient_language if speaker == "patient" else session.doctor_language
        confidence = None
        if audio is not None:
            data = await audio.read()
            if not data:
                raise HTTPException(422, "empty audio")
            if len(data) > settings.max_audio_bytes:
                raise HTTPException(413, "audio too large")
            try:
                transcript = await providers.stt.transcribe(
                    data, language, filename=audio.filename or "audio.webm", content_type=audio.content_type or "audio/webm"
                )
            except ProviderError:
                raise HTTPException(502, "speech recognition failed")
            spoken, confidence = transcript.text, transcript.confidence
        elif text and text.strip():
            spoken = text.strip()
        else:
            raise HTTPException(422, "provide audio or text")
        if not spoken:
            raise HTTPException(422, "could not transcribe audio, please repeat")
        try:
            return await process_turn(session, providers, speaker, spoken, confidence, speak)
        except OverflowError:
            raise HTTPException(409, "turn limit reached")

    @app.post("/api/sessions/{sid}/prescription")
    async def prescription(sid: str, body: PrescriptionRequest):
        session = session_or_404(sid)
        if not body.prescriber_confirmed:
            raise HTTPException(422, "prescriber confirmation is required")
        items = [i.model_dump() for i in body.items]
        return await process_prescription(session, providers, items, settings.reminder_times)

    @app.get("/api/sessions/{sid}/summary")
    async def summary(sid: str):
        return build_summary(session_or_404(sid))

    @app.post("/api/medication/resolve")
    async def medication_resolve(body: ResolveRequest):
        return resolve(body.spoken)

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/sw.js")
    async def service_worker():
        return FileResponse(STATIC / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})

    @app.get("/manifest.webmanifest")
    async def manifest():
        return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
