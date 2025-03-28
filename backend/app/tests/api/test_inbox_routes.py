from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from typing import List
from app.main import app
from app.database import SessionLocal
from app.models.account import Account
from app.models.user import User
from app.models.account_user import AccountUser
from app.models.inbox import Inbox
from app.models.inbox_member import InboxMember


client = TestClient(app)


@pytest.mark.integration
def test_get_user_inboxes():
    """
    Should return inboxes the user is a member of.
    """
    db = SessionLocal()
    account_id = uuid4()
    user_id = uuid4()

    account = Account(id=account_id, name="Test Account")
    user = User(
        id=user_id,
        name="Test User",
        provider="internal",
        uid=uuid4(),
        encrypted_password="secret",
        sign_in_count=1,
    )
    inbox = Inbox(
        id=uuid4(),
        account_id=account.id,
        name="Inbox Example",
        channel_type="whatsapp",
        channel_id="example-channel",
    )

    db.add_all([account, user, inbox])
    db.commit()

    db.refresh(account)
    db.refresh(user)
    db.refresh(inbox)

    db.add(AccountUser(account_id=account.id, user_id=user.id))
    db.add(InboxMember(user_id=user.id, inbox_id=inbox.id))
    db.commit()

    response = client.get(
        "/inboxes",
        headers={
            "X-Account-ID": str(account.id),
            "X-User-ID": str(user.id),
        },
    )

    assert response.status_code == 200
    inboxes = response.json()
    assert isinstance(inboxes, list)
    assert any(i["id"] == str(inbox.id) for i in inboxes)
