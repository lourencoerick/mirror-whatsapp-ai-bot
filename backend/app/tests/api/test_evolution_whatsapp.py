import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.models.account import Account
from app.models.inbox import Inbox


from app.main import app

client = TestClient(app)

INSTANCE_ID = "680df327-c714-40a3-aec5-86ccbb57fa19"


@pytest.fixture
def setup_test_data():
    """
    Creates a test Account and Inbox, returns useful identifiers.
    """
    db = SessionLocal()

    account_id = uuid4()
    instance_id = INSTANCE_ID

    account = Account(id=account_id, name="Test Account")
    inbox = Inbox(
        id=uuid4(),
        name="Test Inbox",
        account_id=account_id,
        channel_type="whatsapp",
        channel_id=instance_id,
    )

    db.add_all([account, inbox])
    db.commit()

    return {
        "account_id": account_id,
        "instance_id": instance_id,
        "inbox_id": inbox.id,
        "db": db,
    }


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
            "instanceId": INSTANCE_ID,
            "source": "ios",
        },
    }


@pytest.mark.integration
def test_webhook_evolution_valid_payload(setup_test_data, valid_evolution_payload):

    response = client.post(
        "/webhook/evolution_whatsapp",
        # headers={"X-Account-ID": str(account_id)},
        json=valid_evolution_payload,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "message enqueued"
    assert response.json()["source_id"] == "wamid.12345"


@pytest.mark.integration
def test_webhook_evolution_not_treatable_event():
    payload = {"invalid": "structure"}
    response = client.post("/webhook/evolution_whatsapp", json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found for source_id"


@pytest.mark.integration
def test_webhook_evolution_invalid_structure():
    payload = {
        "event": "messages.upsert",
        "invalid": "structure",
        "data": {
            "instanceId": INSTANCE_ID,
        },
    }
    response = client.post("/webhook/evolution_whatsapp", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "No valid message found"


@pytest.mark.integration
def test_webhook_evolution_empty_body():
    response = client.post("/webhook/evolution_whatsapp", data={})
    assert (
        response.status_code == 500
    )  # because JSON decode will fail and raise generic exception
