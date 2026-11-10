import asyncio
import json

from app.config import Settings
from app.main import create_app
from app.providers.base import Providers
from app.providers.mock import MockSTT, MockTTS
from fastapi.testclient import TestClient


class FakeLLM:
    def __init__(self, extraction):
        self.extraction = extraction
        self.calls = []

    async def complete(self, system, user):
        self.calls.append(system)
        if "Return ONLY JSON" in system:
            return "Sure:\n" + json.dumps(self.extraction)
        return user


def client_with(llm):
    return TestClient(create_app(Settings(), Providers(MockSTT(), MockTTS(), llm)))


def start(client, patient="hi", doctor="en"):
    return client.post("/api/sessions", json={"patient_language": patient, "doctor_language": doctor, "consent": True}).json()["id"]


def test_model_supplements_missed_emergency():
    client = client_with(FakeLLM({"present": ["chest_pain", "not_a_real_id"], "denied": []}))
    sid = start(client)
    body = client.post(f"/api/sessions/{sid}/turn", data={"speaker": "patient", "text": "dil par bahut bojh sa lag raha hai"}).json()
    assert body["extraction_source"] == "rules + model"
    assert body["alert"]["id"] == "chest_pain"
    assert [s["concept"] for s in body["extraction"]["symptoms"]] == ["chest_pain"]


def test_model_cannot_override_explicit_denial():
    client = client_with(FakeLLM({"present": ["chest_pain"], "denied": []}))
    sid = start(client)
    body = client.post(f"/api/sessions/{sid}/turn", data={"speaker": "patient", "text": "seene mein dard nahi hai"}).json()
    assert body["alert"] is None
    assert body["extraction"]["symptoms"] == []


def test_model_failure_falls_back_to_rules():
    class Broken:
        async def complete(self, system, user):
            from app.providers.base import ProviderError

            raise ProviderError("down")

    client = client_with(Broken())
    sid = start(client)
    body = client.post(f"/api/sessions/{sid}/turn", data={"speaker": "patient", "text": "seene mein dard hai"}).json()
    assert body["extraction_source"] == "rules (model unavailable)"
    assert body["alert"]["id"] == "chest_pain"


def test_translation_uses_glossary_and_enables_doctor_audio():
    llm = FakeLLM({"present": [], "denied": []})
    client = client_with(llm)
    sid = start(client, patient="hi", doctor="en")
    body = client.post(f"/api/sessions/{sid}/turn", data={"speaker": "doctor", "text": "How long?"}).json()
    assert body["translation_mode"] == "llm"
    assert body["audio"]["base64"]
    client.post(f"/api/sessions/{sid}/turn", data={"speaker": "patient", "text": "teen din se bukhar hai"})
    assert any("bukhar = Fever" in call for call in llm.calls)


def test_regional_language_alert_is_translated_or_falls_back_to_hindi():
    client = client_with(FakeLLM({"present": [], "denied": []}))
    sid = start(client, patient="ta", doctor="en")
    body = client.post(f"/api/sessions/{sid}/turn", data={"speaker": "patient", "text": "seene mein dard hai"}).json()
    assert body["alert"]["language"] == "ta"

    plain = TestClient(create_app(Settings()))
    sid = start(plain, patient="ta", doctor="en")
    body = plain.post(f"/api/sessions/{sid}/turn", data={"speaker": "patient", "text": "seene mein dard hai"}).json()
    assert body["alert"]["language"] == "hi"
