# tests/test_inbox_routes.py (example file name)

import pytest
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


from app.models.account import Account
from app.models.user import User
from app.models.inbox import Inbox
from app.models.inbox_member import InboxMember


# Define API prefix
API_V1_PREFIX = "/api/v1"


@pytest.mark.integration
def test_get_account_inboxes_success(
    client: TestClient,
    db_session: Session,
    test_account: Account,
    test_user: User,
    test_inbox: Inbox,
):
    """
    Should return all inboxes belonging to the authenticated user's account.
    """
    another_inbox = Inbox(
        id=uuid4(),
        account_id=test_account.id,
        name="Another Test Inbox",
        channel_type="whatsapp",
        channel_id="another-channel",
    )

    another_inbox_member = InboxMember(user_id=test_user.id, inbox_id=another_inbox.id)
    db_session.add_all([another_inbox, another_inbox_member])

    db_session.commit()
    db_session.refresh(another_inbox)

    response = client.get(
        f"{API_V1_PREFIX}/inboxes",
    )

    assert response.status_code == 200
    inboxes_response = response.json()
    assert isinstance(inboxes_response, list)

    assert len(inboxes_response) >= 2
    inbox_ids_in_response = {inbox_data["id"] for inbox_data in inboxes_response}
    assert str(test_inbox.id) in inbox_ids_in_response
    assert str(another_inbox.id) in inbox_ids_in_response

    first_inbox_data = next(
        (ib for ib in inboxes_response if ib["id"] == str(test_inbox.id)), None
    )
    assert first_inbox_data is not None
    assert first_inbox_data["name"] == test_inbox.name
    assert first_inbox_data["channel_type"] == test_inbox.channel_type


@pytest.mark.integration
def test_get_account_inboxes_unauthenticated(unauthenticated_client: TestClient):
    """
    Should return 403 Forbidden when no authentication is provided.
    """
    response = unauthenticated_client.get(
        f"{API_V1_PREFIX}/inboxes",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.integration
def test_get_account_inboxes_no_inboxes(
    client: TestClient,
    db_session: Session,
    test_account: Account,
):
    """
    Should return an empty list when the account has no inboxes.
    """
    response = client.get(
        f"{API_V1_PREFIX}/inboxes",
    )

    assert response.status_code == 200
    inboxes_response = response.json()
    assert isinstance(inboxes_response, list)
    assert len(inboxes_response) == 0
