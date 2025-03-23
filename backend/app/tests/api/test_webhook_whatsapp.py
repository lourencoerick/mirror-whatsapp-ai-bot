from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.mark.integration
def test_evolution_webhook_valid(monkeypatch):
    # Simula enfileiramento da mensagem com sucesso
    monkeypatch.setattr("app.api.webhook_routes.queue.enqueue", lambda msg: True)

    payload = {
        "event": "messages.upsert",
        "sender": "evolution",
        "data": {
            "instanceId": "minha-instancia",
            "messageType": "chat",
            "messageTimestamp": 1711234567,
            "message": {"conversation": "Oi! Teste webhook"},
            "key": {
                "id": "MSG123",
                "remoteJid": "5511941986775@s.whatsapp.net",
                "fromMe": False,
            },
        },
    }

    response = client.post("/webhook/evolution_whatsapp", json=payload)
    assert response.status_code == 202
    assert response.json() == {"status": "message enqueued", "source_id": "MSG123"}


@pytest.mark.integration
def test_evolution_webhook_invalid():
    payload = {"invalid": "data"}

    response = client.post("/webhook/evolution_whatsapp", json=payload)
    assert response.status_code == 400
    assert response.json() == {"detail": "No valid message found"}
