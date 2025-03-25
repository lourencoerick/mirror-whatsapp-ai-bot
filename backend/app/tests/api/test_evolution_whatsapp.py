import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    client_app = TestClient(app)
    client_app.headers.update({"X-Account-ID": "1"})
    return client_app


@pytest.fixture
def valid_evolution_payload():
    return {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511941986775@s.whatsapp.net",
                "fromMe": False,
                "id": "wamid.12345",
            },
            "pushName": "LL",
            "message": {"conversation": "Olá, isso é um teste!"},
            "messageType": "conversation",
            "messageTimestamp": 1742771256,
            "instanceId": "680df327-c714-40a3-aec5-86ccbb57fa19",
            "source": "ios",
        },
    }


@pytest.mark.integration
def test_webhook_evolution_valid_payload(client, valid_evolution_payload):
    response = client.post("/webhook/evolution_whatsapp", json=valid_evolution_payload)
    assert response.status_code == 202
    assert response.json()["status"] == "message enqueued"
    assert response.json()["source_id"] == "wamid.12345"


@pytest.mark.integration
def test_webhook_evolution_invalid_structure(client):
    payload = {"invalid": "structure"}
    response = client.post("/webhook/evolution_whatsapp", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "No valid message found"


@pytest.mark.integration
def test_webhook_evolution_empty_body(client):
    response = client.post("/webhook/evolution_whatsapp", data={})
    assert (
        response.status_code == 500
    )  # because JSON decode will fail and raise generic exception
