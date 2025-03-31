import pytest
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User
from app.models.inbox import Inbox
from app.models.conversation import Conversation
from app.models.contact_inbox import ContactInbox
from app.models.contact import Contact
from app.models.inbox_member import InboxMember

# Define API prefix
API_V1_PREFIX = "/api/v1"


@pytest.mark.integration
def test_get_inbox_conversations_success(
    client: TestClient, db_session: Session, test_inbox: Inbox, test_account: Account
):
    """
    Test fetching conversations for a specific inbox successfully.
    Requires auth context to verify inbox ownership.
    """
    # Arrange: Create necessary data like Contact, ContactInbox, Conversation
    contact = Contact(id=uuid4(), account_id=test_account.id, phone_number="111")
    contact_inbox = ContactInbox(
        id=uuid4(), contact=contact, inbox=test_inbox, source_id="test"
    )
    conversation = Conversation(
        id=uuid4(),
        account=test_account,
        inbox=test_inbox,
        contact_inbox=contact_inbox,
        status="teste",
    )
    db_session.add_all([contact, contact_inbox, conversation])
    db_session.commit()

    # Act: Call the endpoint using the authenticated client
    response = client.get(
        f"{API_V1_PREFIX}/inboxes/{test_inbox.id}/conversations?limit=5&offset=0",
    )

    # Assert
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    # Add more specific assertions about the returned data if needed


@pytest.mark.integration
def test_get_user_conversations_success(
    client: TestClient,
    db_session: Session,
    test_user: User,
    test_account: Account,
    test_inbox: Inbox,
):
    """
    Test fetching conversations visible to the authenticated user.
    """
    contact = Contact(id=uuid4(), account_id=test_account.id, phone_number="222")
    contact_inbox = ContactInbox(
        id=uuid4(), contact=contact, inbox=test_inbox, source_id="test2"
    )
    conversation = Conversation(
        id=uuid4(),
        account=test_account,
        inbox=test_inbox,
        contact_inbox=contact_inbox,
        status="open",
    )
    # Link user to inbox if find_all_by_user checks membership
    inbox_member = InboxMember(user=test_user, inbox=test_inbox)
    db_session.add_all([contact, contact_inbox, conversation, inbox_member])
    db_session.commit()

    # Act
    response = client.get(
        f"{API_V1_PREFIX}/conversations?limit=5&offset=0",
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Assert based on the conversation created


@pytest.mark.integration
def test_start_conversation_success(
    client: TestClient, db_session: Session, test_inbox: Inbox, test_account: Account
):
    """
    Should successfully create a conversation via the authenticated endpoint.
    """
    # Arrange: Inbox already created by fixture

    # Act
    response = client.post(
        f"{API_V1_PREFIX}/inboxes/{test_inbox.id}/conversations",
        # No X-Account-ID header needed
        json={"phone_number": "5511988888888"},
    )

    # Assert
    assert response.status_code == 200  # Or 201 if you changed it
    data = response.json()
    assert "conversation_id" in data
    # Verify conversation, contact, contact_inbox were created in DB
    conv = (
        db_session.query(Conversation)
        .filter(Conversation.id == UUID(data["conversation_id"]))
        .first()
    )
    assert conv is not None
    assert conv.account_id == test_account.id
    assert conv.inbox_id == test_inbox.id


@pytest.mark.integration
def test_start_conversation_inbox_not_found_or_unauthorized(
    client: TestClient, db_session: Session, test_account: Account
):
    """
    Should return 404 when inbox doesn't exist or belongs to another account,
    even if the user is authenticated.
    """
    # Arrange: Create an inbox belonging to a *different* account
    other_account = Account(id=uuid4(), name="Other Account")
    other_inbox = Inbox(
        id=uuid4(),
        account=other_account,
        name="Other Inbox",
        channel_type="whatsapp",
        channel_id="other_134",
    )
    db_session.add_all([other_account, other_inbox])
    db_session.commit()

    # Act: Try to access non-existent inbox
    response_non_existent = client.post(
        f"{API_V1_PREFIX}/inboxes/{str(uuid4())}/conversations",
        json={"phone_number": "5511977777777"},
    )
    # Act: Try to access inbox of another account
    response_unauthorized = client.post(
        f"{API_V1_PREFIX}/inboxes/{other_inbox.id}/conversations",
        json={"phone_number": "5511966666666"},
    )

    # Assert
    assert response_non_existent.status_code == 404
    assert (
        "Inbox not found or unauthorized" in response_non_existent.json()["detail"]
    )  # Check detail message

    assert (
        response_unauthorized.status_code == 404
    )  # Endpoint logic should return 404 if inbox check fails
    assert "Inbox not found or unauthorized" in response_unauthorized.json()["detail"]


@pytest.mark.integration
def test_start_conversation_unauthenticated(unauthenticated_client: TestClient):
    """
    Should return 403 Forbidden when no authentication is provided.
    (HTTPBearer returns 403 if Authorization header is missing)
    """
    # Act: Use the client WITHOUT the auth override
    response = unauthenticated_client.post(
        f"{API_V1_PREFIX}/inboxes/{str(uuid4())}/conversations",
        json={"phone_number": "5511955555555"},
    )

    # Assert: Expect 403 because HTTPBearer requires the Authorization header
    assert response.status_code == 403
    assert (
        response.json()["detail"] == "Not authenticated"
    )  # Default detail for HTTPBearer
