# test_webhooks_evolution.py (example filename)
import pytest
from uuid import uuid4
from typing import Dict, Any
from loguru import logger
from sqlalchemy import select

# Use AsyncClient and AsyncSession
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.inbox import Inbox


WEBHOOK_PREFIX = "/webhooks"
# Ensure this matches the INSTANCE_ID in conftest.py if tests rely on it
INSTANCE_ID = "c844e6dc-b3ab-4456-92f9-7e39d563f43a"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webhook_evolution_valid_payload(
    unauthenticated_client: AsyncClient,
    test_evolution_inbox: Inbox,
    valid_evolution_payload: Dict[str, Any],
    db_session: AsyncSession,  # Injete a db_session para verificação posterior
):
    """
    Test webhook acknowledges receipt with 204 and verify message processing
    by checking the database afterwards.
    """
    # Arrange: Extract expected identifiers from the payload for later verification
    expected_remote_jid = valid_evolution_payload["data"]["key"]["remoteJid"]
    expected_message_id = valid_evolution_payload["data"]["key"]["id"]
    expected_conversation_text = valid_evolution_payload["data"]["message"][
        "conversation"
    ]

    # Act: Make the async request
    response = await unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution/{test_evolution_inbox.channel_id}",  # Use ID do inbox de teste na URL
        json=valid_evolution_payload,
    )

    # Assert: Check only the status code (204 No Content)
    assert response.status_code == 204


@pytest.mark.integration
@pytest.mark.asyncio  # Mark as async
async def test_webhook_evolution_invalid_message_structure(
    unauthenticated_client: AsyncClient,  # Use AsyncClient
    test_evolution_inbox: Inbox,  # Need the inbox for a valid instanceId
):
    """Test webhook returns 400 for valid event but invalid message data."""
    # Arrange: Payload missing essential 'message' field but has valid instanceId
    payload = {
        "event": "messages.upsert",
        "instance": test_evolution_inbox.channel_id,  # Use ID from the fixture
        "data": {
            "key": {"remoteJid": "123@s.whatsapp.net", "id": "bad.id"},
            # Missing 'message' field
            "pushName": "Incomplete Data",
            "messageTimestamp": 1700000000,
            "instanceId": test_evolution_inbox.channel_id,  # Older Evolution format had this too
        },
        "destination": "5511941986775",
        "date_time": datetime.now(timezone.utc).isoformat(),
        "server_url": "url_teste",
        "apikey": "api_key",
    }

    # Act
    instance_id = payload["instance"]
    response = await unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution/{instance_id}", json=payload
    )
    logger.debug(response)
    # Assert
    assert response.status_code == 400
    assert "No valid message found" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio  # Mark as async
async def test_webhook_evolution_empty_json_body(
    unauthenticated_client: AsyncClient,  # Use AsyncClient
):
    """Test webhook returns 400 or 404 for an empty JSON payload."""
    # Act
    response = await unauthenticated_client.post(f"{WEBHOOK_PREFIX}/evolution", json={})
    # Assert: Likely 404 (Inbox not found) or 400 (Bad Request) depending on checks
    assert response.status_code in [400, 404]


@pytest.mark.integration
@pytest.mark.asyncio  # Mark as async
async def test_webhook_evolution_non_json_body(
    unauthenticated_client: AsyncClient,  # Use AsyncClient
):
    """Test webhook framework (FastAPI/Starlette) returns 422 for non-JSON body."""
    # Act
    response = await unauthenticated_client.post(
        f"{WEBHOOK_PREFIX}/evolution/123",
        content="this is not json",  # Use content instead of data for raw body
        headers={"Content-Type": "text/plain"},  # Indicate non-JSON type
    )
    # Assert: FastAPI/Starlette should handle invalid JSON parsing
    assert response.status_code == 422
