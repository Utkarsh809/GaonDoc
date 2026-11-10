import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(Settings())) as c:
        yield c


@pytest.fixture
def session(client):
    response = client.post("/api/sessions", json={"patient_language": "hi", "doctor_language": "en", "consent": True})
    assert response.status_code == 201
    return response.json()["id"]
