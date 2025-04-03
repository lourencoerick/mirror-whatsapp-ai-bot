import pytest
from uuid import uuid4, UUID
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.account import Account
from app.models.user import User
from app.models.inbox import Inbox
from app.models.conversation import Conversation
from app.models.contact_inbox import ContactInbox
from app.models.contact import Contact
from app.models.inbox_member import InboxMember

API_V1_PREFIX = "/api/v1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_inbox_conversations_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_inbox: Inbox,
    test_account: Account,
):
    """Test fetching conversations for a specific inbox successfully."""
    # Arrange
    contact = Contact(
        id=uuid4(), account_id=test_account.id, phone_number="111_inbox_test"
    )
    contact_inbox = ContactInbox(
        id=uuid4(),
        contact_id=contact.id,
        inbox_id=test_inbox.id,
        source_id="ci_source_inbox",
    )
    conversation = Conversation(
        id=uuid4(),
        account_id=test_account.id,
        inbox_id=test_inbox.id,
        contact_inbox_id=contact_inbox.id,
        status="open",
    )
    db_session.add_all([contact, contact_inbox, conversation])
    await db_session.commit()

    # Act
    response = await client.get(
        f"{API_V1_PREFIX}/inboxes/{test_inbox.id}/conversations?limit=5&offset=0",
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    found = any(item["id"] == str(conversation.id) for item in data)
    assert (
        found
    ), f"Created conversation {conversation.id} not found in response for inbox {test_inbox.id}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_user_conversations_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_account: Account,
    test_inbox: Inbox,
):
    """Test fetching conversations visible to the authenticated user."""
    # Arrange
    contact = Contact(
        id=uuid4(), account_id=test_account.id, phone_number="222_user_test"
    )
    contact_inbox = ContactInbox(
        id=uuid4(),
        contact_id=contact.id,
        inbox_id=test_inbox.id,
        source_id="ci_source_user",
    )
    conversation = Conversation(
        id=uuid4(),
        account_id=test_account.id,
        inbox_id=test_inbox.id,
        contact_inbox_id=contact_inbox.id,
        status="open",
    )
    # Assumes test_user is already a member of test_inbox via fixture setup
    db_session.add_all([contact, contact_inbox, conversation])
    await db_session.commit()

    # Act
    response = await client.get(
        f"{API_V1_PREFIX}/conversations?limit=10&offset=0",
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    found = any(item["id"] == str(conversation.id) for item in data)
    assert found, f"Conversation {conversation.id} not found in user's general list"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_conversation_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_inbox: Inbox,
    test_account: Account,
):
    """Should successfully create a conversation via the endpoint."""
    # Arrange
    phone_number_to_create = "5511988888888"

    # Act
    response = await client.post(
        f"{API_V1_PREFIX}/inboxes/{test_inbox.id}/conversations",
        json={"phone_number": phone_number_to_create},
    )

    # Assert
    assert response.status_code == 200  # Or 201 if that's what you return
    data = response.json()
    assert "conversation_id" in data
    new_conversation_id = UUID(data["conversation_id"])

    # Verify conversation exists in DB
    stmt = select(Conversation).where(Conversation.id == new_conversation_id)
    result = await db_session.execute(stmt)
    conv = result.scalars().first()

    assert conv is not None, "Conversation not found in database after creation"
    assert conv.account_id == test_account.id
    assert conv.inbox_id == test_inbox.id

    # Verify related contact and contact_inbox
    stmt_ci = select(ContactInbox).where(ContactInbox.id == conv.contact_inbox_id)
    result_ci = await db_session.execute(stmt_ci)
    ci = result_ci.scalars().first()
    assert ci is not None

    stmt_c = select(Contact).where(Contact.id == ci.contact_id)
    result_c = await db_session.execute(stmt_c)
    contact = result_c.scalars().first()
    assert contact is not None
    assert contact.phone_number == phone_number_to_create


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_conversation_inbox_not_found_or_unauthorized(
    client: AsyncClient,
    db_session: AsyncSession,
    test_account: Account,  # Required by other_inbox
):
    """Should return 404 when inbox doesn't exist or belongs to another account."""
    # Arrange: Create an inbox belonging to a different account
    other_account = Account(id=uuid4(), name="Unauthorized Account")
    other_inbox = Inbox(
        id=uuid4(),
        account=other_account,  # Belongs to other account
        name="Other Inbox",
        channel_type="whatsapp",
        channel_id="other_channel_id_134",
    )
    db_session.add_all([other_account, other_inbox])
    await db_session.commit()

    # Act & Assert: Test with a non-existent inbox ID
    non_existent_inbox_id = uuid4()
    response_non_existent = await client.post(
        f"{API_V1_PREFIX}/inboxes/{non_existent_inbox_id}/conversations",
        json={"phone_number": "5511977777777"},
    )
    assert response_non_existent.status_code == 404
    assert "Inbox not found or unauthorized" in response_non_existent.json()["detail"]

    # Act & Assert: Test with an inbox ID belonging to the other account
    response_unauthorized = await client.post(
        f"{API_V1_PREFIX}/inboxes/{other_inbox.id}/conversations",
        json={"phone_number": "5511966666666"},
    )
    assert response_unauthorized.status_code == 404
    assert "Inbox not found or unauthorized" in response_unauthorized.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_conversation_unauthenticated(
    unauthenticated_client: AsyncClient,
):
    """Should return 403 Forbidden when no authentication is provided."""
    # Arrange
    some_inbox_id = uuid4()

    # Act
    response = await unauthenticated_client.post(
        f"{API_V1_PREFIX}/inboxes/{some_inbox_id}/conversations",
        json={"phone_number": "5511955555555"},
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"
