import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime, timezone

from app.models.conversation import Conversation, ConversationStatusEnum
from app.models.contact import Contact
from app.models.inbox import Inbox
from app.models.user import User
from app.models.contact_inbox import ContactInbox

# Removed unused schema import: ConversationSearchResult

pytestmark = pytest.mark.asyncio

API_V1_PREFIX = "/api/v1"


@pytest_asyncio.fixture(scope="function")
async def test_conversation(
    db_session: AsyncSession,
    test_account: "Account",
    test_inbox: Inbox,
    test_contact: Contact,
) -> Conversation:
    """Creates a persisted test conversation (PENDING, 5 unread)."""
    contact_inbox = await db_session.scalar(
        select(ContactInbox).filter_by(
            contact_id=test_contact.id, inbox_id=test_inbox.id
        )
    )
    if not contact_inbox:
        contact_inbox = ContactInbox(
            id=uuid4(),
            contact_id=test_contact.id,
            inbox_id=test_inbox.id,
            source_id=f"test-source-{uuid4().hex}",
        )
        db_session.add(contact_inbox)
        await db_session.flush()
        await db_session.refresh(contact_inbox)

    conversation = Conversation(
        id=uuid4(),
        account_id=test_account.id,
        inbox_id=test_inbox.id,
        contact_inbox_id=contact_inbox.id,
        status=ConversationStatusEnum.PENDING,
        unread_agent_count=5,
        additional_attributes={
            "contact_name": test_contact.name,
            "phone_number": test_contact.phone_number,
            "profile_picture_url": test_contact.profile_picture_url,
            "last_message": {
                "id": str(uuid4()),
                "content": "Initial message",
                "sent_at": None,
            },
        },
        last_message_at=datetime.now(timezone.utc),  # Add timestamp
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.refresh(conversation)
    return conversation


async def test_update_conversation_status_to_closed(
    client: AsyncClient,
    db_session: AsyncSession,
    test_conversation: Conversation,
):
    """
    Test updating conversation status to CLOSED resets unread count.
    """
    conversation_id = test_conversation.id
    initial_unread_count = test_conversation.unread_agent_count
    assert initial_unread_count > 0

    update_payload = {"status": ConversationStatusEnum.CLOSED.value}

    response = await client.put(
        f"{API_V1_PREFIX}/conversations/{conversation_id}/status", json=update_payload
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(conversation_id)
    assert response_data["status"] == ConversationStatusEnum.CLOSED.value
    assert response_data["unread_agent_count"] == 0

    await db_session.refresh(test_conversation)
    assert test_conversation.status == ConversationStatusEnum.CLOSED
    assert test_conversation.unread_agent_count == 0


async def test_update_conversation_status_to_active_does_not_reset_unread(
    client: AsyncClient,
    db_session: AsyncSession,
    test_conversation: Conversation,
):
    """
    Test updating conversation status to HUMAN_ACTIVE does not reset unread count.
    """
    conversation_id = test_conversation.id
    initial_unread_count = test_conversation.unread_agent_count
    initial_status = test_conversation.status
    assert initial_unread_count > 0
    assert initial_status == ConversationStatusEnum.PENDING

    update_payload = {"status": ConversationStatusEnum.HUMAN_ACTIVE.value}

    response = await client.put(
        f"{API_V1_PREFIX}/conversations/{conversation_id}/status", json=update_payload
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(conversation_id)
    assert response_data["status"] == ConversationStatusEnum.HUMAN_ACTIVE.value
    assert (
        response_data["unread_agent_count"] == initial_unread_count
    )  # Check unchanged

    await db_session.refresh(test_conversation)
    assert test_conversation.status == ConversationStatusEnum.HUMAN_ACTIVE
    assert (
        test_conversation.unread_agent_count == initial_unread_count
    )  # Check unchanged


async def create_test_conversation(  # Helper function kept for clarity
    db: AsyncSession,
    account: "Account",
    inbox: Inbox,
    contact: Contact,
    status: ConversationStatusEnum,
    unread_count: int,
) -> Conversation:
    """Helper to create a conversation with specific status and unread count."""
    contact_inbox = await db.scalar(
        select(ContactInbox).filter_by(contact_id=contact.id, inbox_id=inbox.id)
    )
    if not contact_inbox:
        contact_inbox = ContactInbox(
            id=uuid4(),
            contact_id=contact.id,
            inbox_id=inbox.id,
            source_id=f"helper-{uuid4().hex}",
        )
        db.add(contact_inbox)
        await db.flush()
        await db.refresh(contact_inbox)

    conversation = Conversation(
        id=uuid4(),
        account_id=account.id,
        inbox_id=inbox.id,
        contact_inbox_id=contact_inbox.id,
        status=status,
        unread_agent_count=unread_count,
        additional_attributes={
            "contact_name": contact.name,
            "phone_number": contact.phone_number,
            "profile_picture_url": contact.profile_picture_url,
            "last_message": {
                "id": str(uuid4()),
                "content": f"Msg for {status.value}",
                "sent_at": None,
            },
        },
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(conversation)
    await db.flush()
    await db.refresh(conversation)
    return conversation


async def test_list_conversations_filter_by_status_pending(
    client: AsyncClient,
    db_session: AsyncSession,
    test_account: "Account",
    test_inbox: Inbox,
    test_contact: Contact,
    test_user: User,
):
    """
    Test GET /conversations filtering by status=PENDING.
    """
    conv_pending_1 = await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.PENDING,
        unread_count=1,
    )
    conv_pending_2 = await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.PENDING,
        unread_count=0,
    )
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.HUMAN_ACTIVE,
        unread_count=1,
    )  # Unused variable removed
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.CLOSED,
        unread_count=0,
    )  # Unused variable removed

    # Commit needed before API call reads from DB
    await db_session.commit()

    response = await client.get(
        f"{API_V1_PREFIX}/conversations",
        params={"status": ConversationStatusEnum.PENDING.value},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2

    returned_ids = {item["id"] for item in response_data}
    expected_ids = {str(conv_pending_1.id), str(conv_pending_2.id)}
    assert returned_ids == expected_ids

    for item in response_data:
        assert item["status"] == ConversationStatusEnum.PENDING.value


async def test_list_conversations_filter_by_multiple_statuses(
    client: AsyncClient,
    db_session: AsyncSession,
    test_account: "Account",
    test_inbox: Inbox,
    test_contact: Contact,
    test_user: User,
):
    """
    Test GET /conversations filtering by multiple statuses (PENDING, HUMAN_ACTIVE).
    """
    conv_pending = await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.PENDING,
        unread_count=1,
    )
    conv_active = await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.HUMAN_ACTIVE,
        unread_count=0,
    )
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.CLOSED,
        unread_count=0,
    )

    await db_session.commit()

    # Pass params as a list of tuples for multiple values with the same key
    response = await client.get(
        f"{API_V1_PREFIX}/conversations",
        params=[
            ("status", ConversationStatusEnum.PENDING.value),
            ("status", ConversationStatusEnum.HUMAN_ACTIVE.value),
        ],
    )

    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2

    returned_ids = {item["id"] for item in response_data}
    expected_ids = {str(conv_pending.id), str(conv_active.id)}
    assert returned_ids == expected_ids

    returned_statuses = {item["status"] for item in response_data}
    expected_statuses = {
        ConversationStatusEnum.PENDING.value,
        ConversationStatusEnum.HUMAN_ACTIVE.value,
    }
    assert returned_statuses == expected_statuses


async def test_list_conversations_filter_by_has_unread_true(
    client: AsyncClient,
    db_session: AsyncSession,
    test_account: "Account",
    test_inbox: Inbox,
    test_contact: Contact,
    test_user: User,
):
    """
    Test GET /conversations filtering by has_unread=true.
    """
    conv_unread_1 = await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.PENDING,
        unread_count=5,
    )
    conv_unread_2 = await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.HUMAN_ACTIVE,
        unread_count=1,
    )
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.PENDING,
        unread_count=0,
    )
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.CLOSED,
        unread_count=0,
    )

    await db_session.commit()

    response = await client.get(
        f"{API_V1_PREFIX}/conversations",
        params={"has_unread": "true"},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2

    returned_ids = {item["id"] for item in response_data}
    expected_ids = {str(conv_unread_1.id), str(conv_unread_2.id)}
    assert returned_ids == expected_ids

    for item in response_data:
        assert item["unread_agent_count"] > 0


async def test_list_conversations_filter_by_status_and_has_unread(
    client: AsyncClient,
    db_session: AsyncSession,
    test_account: "Account",
    test_inbox: Inbox,
    test_contact: Contact,
    test_user: User,
):
    """
    Test GET /conversations filtering by status=PENDING and has_unread=true.
    """
    conv_pending_unread = await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.PENDING,
        unread_count=3,
    )
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.PENDING,
        unread_count=0,
    )
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.HUMAN_ACTIVE,
        unread_count=2,
    )
    await create_test_conversation(
        db_session,
        test_account,
        test_inbox,
        test_contact,
        status=ConversationStatusEnum.CLOSED,
        unread_count=0,
    )

    await db_session.commit()

    response = await client.get(
        f"{API_V1_PREFIX}/conversations",
        params={"status": ConversationStatusEnum.PENDING.value, "has_unread": "true"},
    )

    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 1

    returned_conversation = response_data[0]
    assert returned_conversation["id"] == str(conv_pending_unread.id)
    assert returned_conversation["status"] == ConversationStatusEnum.PENDING.value
    assert returned_conversation["unread_agent_count"] > 0
