import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.queue.iqueue import IQueue

client = TestClient(app)


# Simulador (mock) de fila para testes
class MockQueue(IQueue):
    def __init__(self):
        self.messages = []

    def enqueue(self, message: dict):
        self.messages.append(message)

    def dequeue(self) -> dict:
        return self.messages.pop(0) if self.messages else None


# Simula payload da Evolution API
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
            "message": {"conversation": "Mensagem de teste"},
            "messageType": "conversation",
            "messageTimestamp": 1742607528,
        },
    }


@pytest.fixture
def monkeypatch_queue(monkeypatch):
    from app.api import webhook_routes

    # Substitui a fila real pela mockada
    webhook_routes.queue = MockQueue()
    return webhook_routes.queue


@pytest.mark.integration
def test_webhook_evolution_with_mock(monkeypatch_queue, valid_evolution_payload):
    response = client.post("/webhook/evolution_whatsapp", json=valid_evolution_payload)

    assert response.status_code == 202
    assert response.json()["status"] == "message enqueued"
    assert len(monkeypatch_queue.messages) == 1

    message = monkeypatch_queue.dequeue()
    assert message["content"] == "Mensagem de teste"
    assert message["source_id"] == "wamid.12345"
