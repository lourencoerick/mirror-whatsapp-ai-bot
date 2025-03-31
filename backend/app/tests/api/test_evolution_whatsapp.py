import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker, Session
from typing import Dict, Any

from app.models.inbox import Inbox

WEBHOOK_PREFIX = "/webhooks"
INSTANCE_ID = "680df327-c714-40a3-aec5-86ccbb57fa19"


@pytest.mark.integration
def test_webhook_evolution_valid_payload(
    unauthenticated_client: TestClient,
    test_evolution_inbox: Inbox,
    valid_evolution_payload: Dict[str, Any],
    db_session: Session,
):
    """
    Test receiving a valid message payload from Evolution webhook.
    Expects the message to be enqueued successfully.
    """
    response = unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution_whatsapp",
        json=valid_evolution_payload,
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "message enqueued"
    assert data["source_id"] == "wamid.12345"


@pytest.mark.integration
def test_webhook_evolution_not_treatable_event(unauthenticated_client: TestClient):
    """
    Test sending a payload structure that the handler doesn't recognize
    or cannot extract necessary info (like instanceId) from.
    """
    payload = {"event": "some.other.event", "instanceId": "non_existent_instance"}

    response = unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution_whatsapp", json=payload
    )

    assert response.status_code == 404
    assert "Account not found for source_id" in response.json()["detail"]


@pytest.mark.integration
def test_webhook_evolution_invalid_message_structure(
    unauthenticated_client: TestClient,
    test_evolution_inbox: Inbox,  # Include inbox fixture so account exists
):
    """
    Test sending a payload with a recognized event type but invalid 'data'
    structure for message processing.
    """
    # Arrange: Payload missing essential message fields but has valid instanceId
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"id": "bad.id"},
            # Missing 'message' field
            "instanceId": INSTANCE_ID,  # Match the existing inbox's instanceId
        },
    }

    response = unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution_whatsapp", json=payload
    )

    assert response.status_code == 400
    assert "No valid message found" in response.json()["detail"]


@pytest.mark.integration
def test_webhook_evolution_empty_json_body(unauthenticated_client: TestClient):
    """
    Test sending an empty JSON object.
    The handler might return 400 or 404 depending on initial checks.
    """
    response = unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution_whatsapp", json={}
    )
    assert response.status_code in [400, 404]


@pytest.mark.integration
def test_webhook_evolution_non_json_body(unauthenticated_client: TestClient):
    """
    Test sending data that is not valid JSON.
    FastAPI/Starlette should handle this and return 422 Unprocessable Entity.
    """
    response = unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution_whatsapp",
        data="this is not json",
    )
    assert response.status_code == 422
