from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import desc, select, tuple_, asc, delete
from typing import List, Optional
from loguru import logger
from app.models.message import Message
from app.models.inbox import Inbox
from app.api.schemas.message import MessageCreate


async def find_message_by_id(db: AsyncSession, message_id: UUID) -> Optional[Message]:
    """Retrieve a message by its ID with related contact and inbox loaded.

    Args:
        db (AsyncSession): Database session.
        message_id (UUID): The ID of the message to retrieve.

    Returns:
        Optional[Message]: The Message object if found, otherwise None.
    """
    result = await db.execute(
        select(Message)
        .options(joinedload(Message.contact))
        .options(joinedload(Message.inbox))
        .filter_by(id=message_id)
    )
    message = result.scalar_one_or_none()

    if message:
        logger.debug(f"[message] Found message {message.id}")
    else:
        logger.warning(f"[message] Not found: {message_id}")

    return message


async def find_messages_by_conversation(
    db: AsyncSession,
    conversation_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[Message]:
    """Retrieve messages belonging to a specific conversation filtered by account.

    Args:
        db (AsyncSession): SQLAlchemy database session.
        conversation_id (UUID): The ID of the conversation.
        account_id (UUID): The account context to enforce RLS isolation.
        limit (int): Maximum number of messages to return (default is 20).
        offset (int): Number of messages to skip (for pagination).

    Returns:
        List[Message]: A list of messages ordered by message timestamp descending.
    """
    result = await db.execute(
        select(Message)
        .filter_by(account_id=account_id, conversation_id=conversation_id)
        .order_by(desc(Message.sent_at))
        .limit(limit)
        .offset(offset)
    )
    messages = result.scalars().all()
    return messages


async def create_message(db: AsyncSession, message_data: MessageCreate) -> Message:
    """Retrieve a message by inbox_id and source_id, or create one if it doesn't exist.

    Ensures idempotent message handling. Transaction finalization (commit, refresh, rollback)
    should be handled by the caller.

    Args:
        db (AsyncSession): Database session.
        message_data (MessageCreate): The data for the message to create.

    Returns:
        Message: The Message object.

    Raises:
        ValueError: If source_id is not provided in message_data.
    """
    logger.info("[MessageRepo] Creating new message ")

    new_message = Message(
        account_id=message_data.account_id,
        inbox_id=message_data.inbox_id,
        conversation_id=message_data.conversation_id,
        contact_id=message_data.contact_id,
        source_id=message_data.source_id,
        user_id=message_data.user_id,
        direction=message_data.direction,
        message_type=message_data.direction,
        private=message_data.private,
        status=message_data.status,
        sent_at=message_data.message_timestamp,
        content=message_data.content,
        content_type=message_data.content_type,
        content_attributes=message_data.content_attributes,
    )

    db.add(new_message)
    await db.flush()
    logger.info(f"[MessageRepo] New message prepared with ID={new_message.id}")
    return new_message


async def get_or_create_message(
    db: AsyncSession, message_data: MessageCreate
) -> Message:
    """Retrieve a message by inbox_id and source_id, or create one if it doesn't exist.

    Ensures idempotent message handling. Transaction finalization (commit, refresh, rollback)
    should be handled by the caller.

    Args:
        db (AsyncSession): Database session.
        message_data (MessageCreate): The data for the message to create.

    Returns:
        Message: The Message object.

    Raises:
        ValueError: If source_id is not provided in message_data.
    """
    if not message_data.source_id:
        raise ValueError("source_id is required to identify messages")

    # Check for an existing message
    result = await db.execute(
        select(Message)
        .options(selectinload(Message.contact))
        .filter_by(inbox_id=message_data.inbox_id, source_id=message_data.source_id)
    )
    message = result.scalar_one_or_none()

    if message:
        logger.debug(f"[message] Reusing existing message (id={message.id})")
        return message

    # Create new message if one doesn't exist
    new_message = Message(
        account_id=message_data.account_id,
        inbox_id=message_data.inbox_id,
        conversation_id=message_data.conversation_id,
        contact_id=message_data.contact_id,
        source_id=message_data.source_id,
        user_id=message_data.user_id,
        direction=message_data.direction,
        message_type=message_data.direction,
        private=message_data.private,
        status=message_data.status,
        sent_at=message_data.message_timestamp,
        content=message_data.content,
        content_type=message_data.content_type,
        content_attributes=message_data.content_attributes,
    )

    db.add(new_message)
    await db.flush()
    # Removed commit and refresh: the caller should finalize the transaction.
    logger.info(f"[message] Created new message (id={new_message.id})")
    return new_message


async def get_messages_paginated(
    db: AsyncSession,
    *,
    account_id: UUID,
    conversation_id: UUID,
    limit: int = 30,
    before_cursor: Optional[UUID] = None,
    after_cursor: Optional[UUID] = None,
) -> List[Message]:
    """
    Fetch a paginated list of messages for a conversation using cursor-based pagination.

    If 'before_cursor' is provided, fetches messages older than the cursor.
    If 'after_cursor' is provided, fetches messages newer than the cursor.
    If neither cursor is provided, fetches the latest messages.

    Args:
        db (AsyncSession): The SQLAlchemy AsyncSession.
        account_id (UUID): The account ID.
        conversation_id (UUID): The conversation ID.
        limit (int): The maximum number of messages to return.
        before_cursor (Optional[UUID]): The ID of the message before which to fetch older messages.
        after_cursor (Optional[UUID]): The ID of the message after which to fetch newer messages.

    Returns:
        List[Message]: A list of Message objects sorted chronologically (timestamp ASC, id ASC).
    """
    # Base statement selecting messages for the conversation
    stmt = select(Message).where(
        Message.account_id == account_id,
        Message.conversation_id == conversation_id,
    )

    # --- Apply Cursor Logic ---
    target_cursor = after_cursor or before_cursor

    # Fetch the cursor message's timestamp and ID if a cursor is provided
    if target_cursor:
        cursor_stmt = select(Message.sent_at, Message.id).where(
            Message.id == target_cursor
        )
        cursor_result = await db.execute(cursor_stmt)
        cursor_data = cursor_result.first()
        if not cursor_data:
            logger.info(f"Cursor message {target_cursor} not found.")
            return []
        cursor_timestamp, cursor_id = cursor_data

    # --- Filtering ---
    if before_cursor:
        # Fetch messages chronologically before the cursor using tuple comparison.
        print(f"Fetching messages before cursor {before_cursor}")
        stmt = stmt.where(
            tuple_(Message.sent_at, Message.id) < (cursor_timestamp, cursor_id)
        )
        stmt = stmt.order_by(desc(Message.sent_at), desc(Message.id))
    elif after_cursor:
        # Fetch messages chronologically after the cursor using tuple comparison.
        print(f"Fetching messages after cursor {after_cursor}")
        stmt = stmt.where(
            tuple_(Message.sent_at, Message.id) > (cursor_timestamp, cursor_id)
        )
        stmt = stmt.order_by(asc(Message.sent_at), asc(Message.id))
    else:
        # Default case: no cursor provided, fetch latest messages.
        print("Fetching latest messages (no cursor)")
        stmt = stmt.order_by(desc(Message.sent_at), desc(Message.id))

    # --- Apply Limit ---
    stmt = stmt.limit(limit)

    # --- Execute Query ---
    result = await db.execute(stmt)
    messages = result.scalars().all()

    # --- Reverse results if needed ---
    if before_cursor or not after_cursor:
        messages.reverse()
        print("Reversed message list for 'before' or 'latest' fetch.")

    print(f"Returning {len(messages)} messages.")
    return messages


async def update_message_status_by_source_id(
    db: AsyncSession,
    *,
    account_id: UUID,
    source_id: UUID,
    status: str,
) -> None:
    result = await db.execute(
        select(Message).filter_by(source_id=source_id, account_id=account_id)
    )
    message = result.scalar_one_or_none()

    if message:
        logger.debug(f"[message] Found message {message.id} via source_id {source_id}")
        if message.status != status:
            message.status = status
            db.add(message)
    else:
        logger.warning(f"[message] Not found: {source_id}")
        return


async def delete_messages_by_conversation(
    db: AsyncSession, conversation_id: UUID
) -> int:
    """
    Deletes all messages associated with a specific conversation ID.

    Args:
        db: The SQLAlchemy async session.
        conversation_id: The UUID of the conversation whose messages are to be deleted.

    Returns:
        The number of messages deleted.
    """
    logger.warning(f"Deleting all messages for conversation_id: {conversation_id}")
    stmt = delete(Message).where(Message.conversation_id == conversation_id)
    try:
        result = await db.execute(stmt)

        deleted_count = result.rowcount

        logger.info(
            f"Deleted {deleted_count} messages for conversation {conversation_id}."
        )
        return deleted_count
    except Exception as e:
        logger.error(f"Error deleting messages for conversation {conversation_id}: {e}")
        # Propaga a exceção para permitir rollback na chamada
        raise
