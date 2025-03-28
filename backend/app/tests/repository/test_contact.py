import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.inbox import Inbox
from app.models.user import User
from app.models.account import Account
from app.models.account_user import AccountUser
from uuid import uuid4, UUID
from loguru import logger

client = TestClient(app)


@pytest.fixture
def setup_test_data():
    """
    Creates test data in the database and yields useful objects.
    Rolls back any changes after the test.
    """
    db = SessionLocal()
    name_suffix = str(uuid4())[:8]
    account = Account(name=f"Test Account {name_suffix}")
    user = User(
        name="John",
        email="john@example.com",
        provider="teste",
        uid=name_suffix,
        encrypted_password=name_suffix,
        sign_in_count=0,
    )
    inbox = Inbox(
        name="Test Inbox",
        channel_type="whatsapp",
        account=account,
        channel_id=f"teste {name_suffix}",
    )

    db.add_all([account, user, inbox])
    db.commit()

    db.refresh(account)
    db.refresh(user)
    db.refresh(inbox)

    db.add(AccountUser(account_id=account.id, user_id=user.id))
    db.commit()

    yield {
        "db": db,
        "account": account,
        "user": user,
        "inbox": inbox,
    }

    # Teardown
    db.rollback()
    db.close()


@pytest.mark.integration
def test_start_conversation_flow(setup_test_data):
    """
    Integration test for starting a conversation by phone number.
    Should create contact, contact_inbox, and conversation if they don’t exist.
    """
    account = setup_test_data["account"]
    inbox = setup_test_data["inbox"]
    logger.debug(f"[test:repo:contact] Account: {account}\n Inbox: {inbox}")
    response = client.post(
        f"/inboxes/{inbox.id}/conversations",
        headers={"X-Account-ID": str(account.id)},
        json={"phone_number": "5511999999999"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "conversation_id" in data
    assert isinstance(UUID(data["conversation_id"]), UUID)
