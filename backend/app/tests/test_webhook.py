from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_webhook_valid_payload(monkeypatch):
    # Mock queue enqueue
    monkeypatch.setattr("app.api.webhook.queue.enqueue", lambda msg: True)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "5561999999999",
                                    "id": "ABGG1234XYZ",
                                    "timestamp": "1692467200",
                                    "text": {"body": "Hello"},
                                    "type": "text",
                                }
                            ]
                        }
                    }
                ],
            }
        ],
    }

    response = client.post("/webhook/whatsapp", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_webhook_invalid_payload():
    payload = {"invalid": "structure"}
    response = client.post("/webhook/whatsapp", json=payload)
    print(response.json())
    assert response.status_code == 400
