def turn(client, sid, speaker, text, **extra):
    return client.post(f"/api/sessions/{sid}/turn", data={"speaker": speaker, "text": text, **extra})


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["provider_mode"] == "mock"


def test_consent_required(client):
    response = client.post("/api/sessions", json={"patient_language": "hi", "doctor_language": "en", "consent": False})
    assert response.status_code == 422


def test_invalid_language_rejected(client):
    response = client.post("/api/sessions", json={"patient_language": "Hindi", "doctor_language": "en", "consent": True})
    assert response.status_code == 422


def test_unknown_session(client):
    assert client.get("/api/sessions/nope/summary").status_code == 404


def test_emergency_alert_with_audio(client, session):
    body = turn(client, session, "patient", "seene mein dard hai aur saans phool rahi hai").json()
    assert body["alert"]["level"] == "emergency"
    assert body["alert"]["language"] == "hi"
    assert body["alert"]["audio"]["base64"]
    assert {"chest_pain", "breathlessness"} <= {f["id"] for f in body["red_flags"]}
    assert body["possible_conditions"][0]["id"] == "acs_rule_out"
    assert "Chest pain" in body["clinical_summary"]


def test_alert_only_fires_once_per_flag(client, session):
    first = turn(client, session, "patient", "seene mein dard hai").json()
    second = turn(client, session, "patient", "seene mein dard hai abhi bhi").json()
    assert first["alert"] is not None
    assert second["alert"] is None
    assert second["new_red_flags"] == []


def test_translation_unavailable_is_reported_not_faked(client, session):
    body = turn(client, session, "doctor", "How long have you had the fever?").json()
    assert body["translation_mode"] == "passthrough"
    assert body["translation_warning"]
    assert body["audio"] is None


def test_same_language_doctor_turn_speaks(client):
    sid = client.post("/api/sessions", json={"patient_language": "hi", "doctor_language": "hi", "consent": True}).json()["id"]
    body = turn(client, sid, "doctor", "kitne din se bukhar hai").json()
    assert body["translation_mode"] == "same"
    assert body["audio"]["mime"] == "audio/wav"


def test_audio_upload_through_stt(client, session):
    response = client.post(
        f"/api/sessions/{session}/turn",
        data={"speaker": "patient"},
        files={"audio": ("a.webm", "teen din se bukhar hai".encode("utf-8"), "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json()["transcript"] == "teen din se bukhar hai"
    assert response.json()["stt_confidence"] == 1.0


def test_undecodable_audio_asks_to_repeat(client, session):
    response = client.post(f"/api/sessions/{session}/turn", data={"speaker": "patient"}, files={"audio": ("a.webm", b"\xff\xfe\x00\x81", "audio/webm")})
    assert response.status_code == 422


def test_turn_requires_input(client, session):
    assert client.post(f"/api/sessions/{session}/turn", data={"speaker": "patient"}).status_code == 422


def test_prescription_requires_prescriber_confirmation(client, session):
    body = {"prescriber_confirmed": False, "items": [{"drug": "Metformin", "pattern": "1-0-1"}]}
    assert client.post(f"/api/sessions/{session}/prescription", json=body).status_code == 422


def test_prescription_guidance_and_summary(client, session):
    turn(client, session, "patient", "mujhe penicillin se allergy hai, teen din se bukhar hai")
    body = {
        "prescriber_confirmed": True,
        "items": [
            {"drug": "Dolo 650", "dose": "1 tablet", "pattern": "1-0-1", "days": 3, "timing": "after_food"},
            {"drug": "Augmentin", "dose": "1 tablet", "pattern": "1-0-1", "days": 5, "timing": "with_food"},
        ],
    }
    guidance = client.post(f"/api/sessions/{session}/prescription", json=body).json()
    assert guidance["spoken"]["language"] == "hi"
    assert guidance["spoken"]["audio"]["base64"]
    assert len(guidance["reminders"]) == 4
    assert "allergy" in {w["type"] for w in guidance["warnings"]}
    summary = client.get(f"/api/sessions/{session}/summary").json()
    assert "Fever (3 days)" in summary["doctor_summary"]
    assert "Prescription:" in summary["doctor_summary"]
    assert "अस्पताल" in summary["patient_summary"]["hi"]


def test_pattern_validation(client, session):
    body = {"prescriber_confirmed": True, "items": [{"drug": "Metformin", "pattern": "abc"}]}
    assert client.post(f"/api/sessions/{session}/prescription", json=body).status_code == 422


def test_medication_resolve_endpoint(client):
    body = client.post("/api/medication/resolve", json={"spoken": "metfarmin"}).json()
    assert body["candidates"][0]["generic"] == "Metformin"
    assert body["needs_confirmation"] is True


def test_session_delete(client, session):
    assert client.delete(f"/api/sessions/{session}").status_code == 204
    assert client.get(f"/api/sessions/{session}/summary").status_code == 404


def test_static_shell_served(client):
    assert "GaonDoc" in client.get("/").text
    assert client.get("/manifest.webmanifest").status_code == 200
    assert client.get("/sw.js").status_code == 200
    assert client.get("/api/health").headers["cache-control"] == "no-store"
