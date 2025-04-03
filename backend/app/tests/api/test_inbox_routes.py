import pytest
from uuid import uuid4, UUID


from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.account import Account
from app.models.user import User
from app.models.inbox import Inbox
from app.models.inbox_member import InboxMember


API_V1_PREFIX = "/api/v1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_account_inboxes_success(
    client: AsyncClient,
    db_session: AsyncSession,
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

    another_inbox_member = InboxMember(
        id=uuid4(),
        user_id=test_user.id,
        inbox_id=another_inbox.id,
    )
    db_session.add_all([another_inbox, another_inbox_member])
    await db_session.flush()
    await db_session.commit()

    await db_session.refresh(another_inbox)

    response = await client.get(
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
@pytest.mark.asyncio
async def test_list_account_inboxes_unauthenticated(
    unauthenticated_client: AsyncClient,
):
    """
    Should return 403 Forbidden when no authentication is provided.
    """

    response = await unauthenticated_client.get(
        f"{API_V1_PREFIX}/inboxes",
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_account_inboxes_no_inboxes(
    client: AsyncClient,
    db_session: AsyncSession,
    test_account: Account,
    test_user: User,
    test_inbox: Inbox,
):
    """
    Should return an empty list when the account's only inbox is deleted.
    """
    stmt_member = select(InboxMember).where(InboxMember.inbox_id == test_inbox.id)
    result_member = await db_session.execute(stmt_member)
    members = result_member.scalars().all()
    for member in members:
        await db_session.delete(member)
    await db_session.flush()

    await db_session.delete(test_inbox)
    await db_session.commit()

    response = await client.get(
        f"{API_V1_PREFIX}/inboxes",
    )

    assert response.status_code == 200
    inboxes_response = response.json()
    assert isinstance(inboxes_response, list)
    assert len(inboxes_response) == 0
