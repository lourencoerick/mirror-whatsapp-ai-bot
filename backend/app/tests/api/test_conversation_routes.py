from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.account import Account
from app.models.user import User
from app.models.account__user import AccountUser
from app.models.inbox import Inbox

client = TestClient(app)


@pytest.mark.integration
def test_get_conversations_success():
    db = SessionLocal()
    account = Account(id=uuid4(), name="Test")
    inbox = Inbox(
        id=uuid4(),
        name="Test Inbox",
        account_id=account.id,
        channel_type="whatsapp",
        channel_id="123",
    )
    db.add_all([account, inbox])
    db.commit()

    response = client.get(
        f"/inboxes/{inbox.id}/conversations?limit=5&offset=0",
        headers={"X-Account-ID": str(account.id)},
    )

    assert response.status_code == 200


@pytest.mark.integration
def test_start_conversation_successful_flow():
    """
    Should successfully create a conversation from a phone number for a valid inbox and account.
    """
    db = SessionLocal()

    # Prepare test data
    account = Account(name="Test Account")
    user = User(
        name="John",
        email="john@example.com",
        provider="internal",
        uid=uuid4(),
        encrypted_password="hahah",
        sign_in_count=0,
    )
    inbox = Inbox(
        name="Support", channel_type="whatsapp", account=account, channel_id="123"
    )
    db.add_all([account, user, inbox])
    db.commit()

    db.refresh(account)
    db.refresh(inbox)
    db.add(AccountUser(account_id=account.id, user_id=user.id))
    db.commit()

    # Make request with valid account and inbox
    response = client.post(
        f"/inboxes/{inbox.id}/conversations",
        headers={"X-Account-ID": str(account.id)},
        json={"phone_number": "5511988888888"},
    )

    assert response.status_code == 200
    assert "conversation_id" in response.json()


@pytest.mark.integration
def test_start_conversation_inbox_not_found():
    """
    Should return 404 when inbox doesn't exist or belongs to another account.
    """
    response = client.post(
        f"/inboxes/{str(uuid4())}/conversations",
        headers={"X-Account-ID": str(uuid4())},
        json={"phone_number": "5511988888888"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Inbox not found or unauthorized"


@pytest.mark.integration
def test_start_conversation_missing_account_header():
    """
    Should return 401 when X-Account-ID header is missing.
    """
    response = client.post(
        f"/inboxes/{str(uuid4())}/conversations",
        json={"phone_number": "5511988888888"},
    )
    assert response.status_code == 401
