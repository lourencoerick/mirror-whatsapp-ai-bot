import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import app
from app.tests.utils.setup_test_data import setup_test_data
from app.database import SessionLocal

client = TestClient(app)


@pytest.fixture
def seeded_data():
    """
    Populate the database with test data and return key identifiers.
    """
    db = SessionLocal()
    from app.models.account import Account
    from app.models.conversation import Conversation

    setup_test_data(db)

    account = db.query(Account).first()
    conversation = db.query(Conversation).first()
    return {
        "account_id": str(account.id),
        "conversation_id": str(conversation.id),
    }


@pytest.mark.integration
def test_get_messages_success(seeded_data):
    """
    Test that GET /conversations/{id}/messages returns messages properly.
    """
    response = client.get(
        f"/conversations/{seeded_data['conversation_id']}/messages?limit=5&offset=0",
        headers={"X-Account-ID": seeded_data["account_id"]},
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
