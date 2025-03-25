import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.mark.integration
def test_get_messages_success():
    response = client.get(
        "/conversations/1/messages?limit=5&offset=0",
        headers={"X-Account-ID": "1"},
    )
    assert response.status_code == 200
    messages = response.json()
    assert isinstance(messages, list)
    if messages:
        message = messages[0]
        assert "id" in message
        assert "content" in message
        assert "direction" in message
        assert "message_type" in message
        assert "content_type" in message
        assert "sent_at" in message
