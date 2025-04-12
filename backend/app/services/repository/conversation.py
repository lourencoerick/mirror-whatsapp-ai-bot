from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, select, or_, and_, cast, Text, literal, func, asc, update
from typing import Optional, List
from loguru import logger
from app.api.schemas.conversation import ConversationSearchResult, MessageSnippet
from app.api.schemas.contact import ContactBase
from app.models.message import Message
from app.models.conversation import Conversation, ConversationStatusEnum
from app.models.contact_inbox import ContactInbox
from app.models.inbox_member import InboxMember

MESSAGE_SNIPPET_LENGTH = 100


async def find_conversation_by_id(
    db: AsyncSession, conversation_id: UUID, account_id: UUID
) -> Optional[Conversation]:
    """Retrieve a conversation by ID.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        conversation_id (UUID): ID of the conversation to retrieve.
        account_id (UUID): ID of the account to which the conversation belongs.

    Returns:
        Optional[Conversation]: The conversation if found, otherwise None.
    """
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.inbox))
        .options(
            selectinload(Conversation.contact_inbox).selectinload(ContactInbox.contact)
        )
        .filter_by(id=conversation_id, account_id=account_id)
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        logger.debug(f"[conversation] Found conversation {conversation.id}")
    else:
        logger.warning(f"[conversation] Not found: {conversation_id}")

    return conversation


async def find_conversations_by_inbox(
    db: AsyncSession,
    inbox_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[Conversation]:
    """Retrieve a list of conversations for a specific inbox.

    Conversations are ordered by the timestamp of the last message in descending order,
    returning the most recent ones first.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        inbox_id (UUID): The inbox identifier.
        account_id (UUID): The account identifier.
        limit (int, optional): Maximum number of records to return (default is 20).
        offset (int, optional): Number of records to skip for pagination (default is 0).

    Returns:
        List[Conversation]: A list of Conversation objects.

    Raises:
        SQLAlchemyError: If an error occurs during the database query.
    """
    try:
        query = (
            select(Conversation)
            .options(
                joinedload(Conversation.contact_inbox).joinedload(ContactInbox.contact)
            )
            .filter(
                Conversation.account_id == account_id, Conversation.inbox_id == inbox_id
            )
            .order_by(desc(Conversation.last_message_at))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(query)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database query error: {e}")
        raise e


async def find_conversation(
    db: AsyncSession,
    inbox_id: UUID,
    contact_inbox_id: UUID,
    account_id: UUID,
) -> Optional[Conversation]:
    """Retrieve a conversation for a contact within an inbox and account.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        inbox_id (UUID): The inbox ID.
        contact_inbox_id (UUID): The contact inbox ID.
        account_id (UUID): The account ID.

    Returns:
        Optional[Conversation]: The conversation if found, otherwise None.
    """
    result = await db.execute(
        select(Conversation).filter_by(
            account_id=account_id,
            inbox_id=inbox_id,
            contact_inbox_id=contact_inbox_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        logger.debug(f"[conversation] Found conversation (id={conversation.id})")
    else:
        logger.info(
            f"[conversation] No conversation found for contact_inbox_id {contact_inbox_id}"
        )

    return conversation


async def get_or_create_conversation(
    db: AsyncSession,
    inbox_id: UUID,
    account_id: UUID,
    contact_inbox_id: UUID,
) -> Conversation:
    """Find or create a conversation for a given contact in an inbox.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        inbox_id (UUID): The inbox ID.
        account_id (UUID): The account ID.
        contact_inbox_id (UUID): The contact inbox ID.

    Returns:
        Conversation: The conversation object.
    """
    conversation = await find_conversation(
        db=db,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        account_id=account_id,
    )

    if conversation:
        return conversation

    logger.info(
        f"[conversation] Creating new conversation for contact_inbox_id {contact_inbox_id}"
    )

    result = await db.execute(
        select(ContactInbox)
        .options(joinedload(ContactInbox.contact))
        .filter_by(id=contact_inbox_id)
    )
    contact_inbox: ContactInbox = result.scalar_one_or_none()

    additional_attributes: dict = {}
    additional_attributes["contact_name"] = contact_inbox.contact.name
    additional_attributes["phone_number"] = contact_inbox.contact.phone_number
    additional_attributes["profile_picture_url"] = (
        contact_inbox.contact.profile_picture_url
    )

    conversation = Conversation(
        account_id=account_id,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        status=ConversationStatusEnum.OPEN,
        additional_attributes=additional_attributes,
    )
    db.add(conversation)
    # Only flush to generate any necessary defaults; commit and refresh are handled by the upper layer.
    await db.flush()
    logger.debug(f"[conversation] Created conversation (id={conversation.id})")
    return conversation


async def find_conversations_by_user(
    db: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
    status: Optional[List[ConversationStatusEnum]] = None,
    has_unread: Optional[bool] = None,
) -> List[Conversation]:
    """Retrieve all conversations accessible to a given user based on inbox membership.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        user_id (UUID): The user ID.
        account_id (UUID): The account ID.
        limit (int): Pagination limit.
        offset (int): Pagination offset.
        status (Optional[List[ConversationStatusEnum]]): List of conversation statuses to filter.
        has_unread (Optional[bool]): Filter for conversations with unread messages.

    Returns:
        List[Conversation]: Conversations accessible to the user.
    """

    inbox_ids_subquery = (
        select(InboxMember.inbox_id).filter(InboxMember.user_id == user_id)
    ).scalar_subquery()

    logger.debug(f"Founded user inbox ids: {inbox_ids_subquery}")
    stmt = (
        select(Conversation)
        .options(
            selectinload(Conversation.contact_inbox).selectinload(ContactInbox.contact)
        )
        .filter(
            Conversation.account_id == account_id,
            Conversation.inbox_id.in_(inbox_ids_subquery),
        )
    )

    if status:
        stmt = stmt.where(Conversation.status.in_(status))

    if has_unread is True:
        stmt = stmt.where(Conversation.unread_agent_count > 0)
    elif has_unread is False:
        stmt = stmt.where(Conversation.unread_agent_count == 0)

    stmt = stmt.order_by(Conversation.updated_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)

    conversations = result.scalars().all()
    return conversations


async def search_conversations(
    db: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    query: str,
    offset: int = 0,
    limit: int = 100,
    status: Optional[List[ConversationStatusEnum]] = None,
    has_unread: Optional[bool] = None,
) -> List[ConversationSearchResult]:
    """Asynchronously search conversations with prioritization.

    The prioritized search checks for:
      1. Matches on contact name or phone number.
      2. Matches on message content.
    If a match is found via message content, the ID of the most recent matching message is included.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        user_id (UUID): The user ID.
        account_id (UUID): The account ID.
        query (str): The search term.
        offset (int): Number of records to skip.
        limit (int): Maximum number of records to return.
        status (Optional[List[ConversationStatusEnum]]): Filter by conversation statuses.
        has_unread (Optional[bool]): Filter conversations by unread message count.

    Returns:
        List[ConversationSearchResult]: A list of prioritized and paginated search results.
    """
    search_term = f"%{query}%"

    user_inbox_ids_subquery = (
        select(InboxMember.inbox_id).filter(InboxMember.user_id == user_id)
    ).scalar_subquery()

    # --- CTE 1: Name and Phone Matches (Rank 1) ---
    name_phone_matches_cte = (
        select(
            Conversation.id.label("conversation_id"),
            literal(1).label("match_rank"),
            literal(None).label("matching_message_id"),
        )
        .select_from(Conversation)
        .filter(
            or_(
                cast(Conversation.additional_attributes["contact_name"], Text).ilike(
                    search_term
                ),
                cast(Conversation.additional_attributes["phone_number"], Text).ilike(
                    search_term
                ),
            )
        )
    ).cte("name_phone_matches")

    # --- CTE 2: Message Content Matches (Rank 2) ---
    message_subquery = (
        select(
            Message.conversation_id,
            Message.id.label("message_id"),
            Message.sent_at,
            func.row_number()
            .over(
                partition_by=Message.conversation_id,
                order_by=desc(Message.sent_at),
            )
            .label("rnk"),
        )
        .select_from(Message)
        .filter(Message.content.ilike(search_term))
        .subquery("message_subquery")
    )

    message_matches_cte = (
        select(
            message_subquery.c.conversation_id.label("conversation_id"),
            literal(2).label("match_rank"),
            message_subquery.c.message_id.label("matching_message_id"),
        )
        .select_from(message_subquery)
        .where(message_subquery.c.rnk == 1)
    ).cte("message_matches")

    # --- CTE 3: Combine Matches using UNION ALL ---
    combined_matches_cte = (
        select(
            name_phone_matches_cte.c.conversation_id,
            name_phone_matches_cte.c.match_rank,
            name_phone_matches_cte.c.matching_message_id,
        ).union_all(
            select(
                message_matches_cte.c.conversation_id,
                message_matches_cte.c.match_rank,
                cast(message_matches_cte.c.matching_message_id, Text).label(
                    "matching_message_id"
                ),
            )
        )
    ).cte("combined_matches")

    # --- CTE 4: Prioritize using ROW_NUMBER ---
    prioritized_matches_cte = (
        select(
            combined_matches_cte.c.conversation_id,
            combined_matches_cte.c.match_rank,
            combined_matches_cte.c.matching_message_id,
            func.row_number()
            .over(
                partition_by=combined_matches_cte.c.conversation_id,
                order_by=asc(combined_matches_cte.c.match_rank),
            )
            .label("priority_rnk"),
        ).select_from(combined_matches_cte)
    ).cte("prioritized_matches")

    # --- Final Query: Select prioritized conversations ---
    final_selection_stmt = (
        select(
            prioritized_matches_cte.c.conversation_id,
            prioritized_matches_cte.c.match_rank,
            prioritized_matches_cte.c.matching_message_id,
            Conversation.last_message_at,
        )
        .select_from(prioritized_matches_cte)
        .join(
            Conversation, prioritized_matches_cte.c.conversation_id == Conversation.id
        )
        .where(prioritized_matches_cte.c.priority_rnk == 1)
        .filter(Conversation.inbox_id.in_(user_inbox_ids_subquery))
    )

    if status:
        final_selection_stmt = final_selection_stmt.where(
            Conversation.status.in_(status)
        )

    if has_unread is True:
        final_selection_stmt = final_selection_stmt.where(
            Conversation.unread_agent_count > 0
        )
    elif has_unread is False:
        final_selection_stmt = final_selection_stmt.where(
            Conversation.unread_agent_count == 0
        )

    final_selection_stmt = (
        final_selection_stmt.order_by(
            asc(prioritized_matches_cte.c.match_rank),
            desc(Conversation.last_message_at),
        )
        .offset(offset)
        .limit(limit)
    )

    final_selection_result = await db.execute(final_selection_stmt)
    prioritized_results = final_selection_result.mappings().all()

    if not prioritized_results:
        return []

    conversation_ids_to_fetch = [res["conversation_id"] for res in prioritized_results]
    result_info_map = {
        res["conversation_id"]: {
            "rank": res["match_rank"],
            "matching_message_id": res["matching_message_id"],
        }
        for res in prioritized_results
    }

    conversations_stmt = select(Conversation).filter(
        Conversation.id.in_(conversation_ids_to_fetch)
    )
    conversations_result = await db.execute(conversations_stmt)
    conversations_map = {conv.id: conv for conv in conversations_result.scalars().all()}
    matched_conversations = [
        conversations_map[id_]
        for id_ in conversation_ids_to_fetch
        if id_ in conversations_map
    ]

    results: List[ConversationSearchResult] = []
    for conv in matched_conversations:
        conv_info = result_info_map[conv.id]
        match_rank = conv_info["rank"]
        pre_fetched_matching_message_id = conv_info["matching_message_id"]

        most_recent_matching_message: Optional[Message] = None
        if match_rank == 2 and pre_fetched_matching_message_id:
            matching_message_stmt = (
                select(Message)
                .where(Message.id == pre_fetched_matching_message_id)
                .limit(1)
            )
            matching_message_result = await db.execute(matching_message_stmt)
            most_recent_matching_message = matching_message_result.scalar_one_or_none()

        try:
            contact = ContactBase(
                name=conv.additional_attributes.get("contact_name"),
                phone_number=conv.additional_attributes.get("phone_number"),
                profile_picture_url=conv.additional_attributes.get(
                    "profile_picture_url"
                ),
            )

            updated_at = conv.last_message_at or conv.updated_at

            last_msg_snippet = MessageSnippet(
                id=conv.additional_attributes.get("last_message")["id"],
                content=conv.additional_attributes.get("last_message")["content"],
                sent_at=conv.last_message_at,
            )

            matching_msg_snippet = None
            if most_recent_matching_message:
                matching_msg_snippet = MessageSnippet(
                    id=most_recent_matching_message.id,
                    content=(most_recent_matching_message.content or "")[
                        :MESSAGE_SNIPPET_LENGTH
                    ],
                    sent_at=most_recent_matching_message.sent_at,
                )

            result_item = ConversationSearchResult(
                id=conv.id,
                contact=contact,
                updated_at=updated_at,
                last_message=last_msg_snippet,
                matching_message=matching_msg_snippet,
            )
            results.append(result_item)
        except Exception as e:
            logger.error(
                f"Error processing conversation {conv.id} for search results: {e}"
            )
            continue

    return results


async def get_message_context(
    db: AsyncSession,
    *,
    account_id: UUID,
    conversation_id: UUID,
    target_message_id: UUID,
    limit_before: int = 5,
    limit_after: int = 5,
) -> List[Message]:
    """Fetch a message and its surrounding context within a conversation.

    Retrieves a specified number of messages before and after a target message,
    including the target message itself.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        account_id (UUID): The account ID.
        conversation_id (UUID): The conversation ID.
        target_message_id (UUID): The ID of the message for context.
        limit_before (int, optional): Maximum messages to fetch before the target (default: 5).
        limit_after (int, optional): Maximum messages to fetch after the target (default: 5).

    Returns:
        List[Message]: A list of Message objects representing the context, ordered chronologically.
    """
    target_msg_stmt = select(Message).where(
        and_(
            Message.account_id == account_id,
            Message.id == target_message_id,
            Message.conversation_id == conversation_id,
        )
    )
    target_msg_result = await db.execute(target_msg_stmt)
    target_message = target_msg_result.scalar_one_or_none()

    if not target_message:
        return []

    before_stmt = (
        select(Message)
        .where(
            and_(
                Message.account_id == account_id,
                Message.conversation_id == conversation_id,
                Message.sent_at < target_message.sent_at,
            )
        )
        .order_by(desc(Message.sent_at), desc(Message.created_at))
        .limit(limit_before)
    )
    before_result = await db.execute(before_stmt)
    messages_before = before_result.scalars().all()

    after_stmt = (
        select(Message)
        .where(
            and_(
                Message.conversation_id == conversation_id,
                Message.sent_at >= target_message.sent_at,
            )
        )
        .order_by(asc(Message.sent_at), asc(Message.id))
        .limit(limit_after + 1)
    )
    after_result = await db.execute(after_stmt)
    messages_after = after_result.scalars().all()

    combined_messages = list(reversed(messages_before)) + messages_after
    return combined_messages


async def update_conversation_status(
    db: AsyncSession,
    *,
    account_id: UUID,
    conversation_id: UUID,
    new_status: ConversationStatusEnum,
) -> Optional[Conversation]:
    """Update the status of a specific conversation.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        account_id (UUID): The account ID.
        conversation_id (UUID): The conversation ID.
        new_status (ConversationStatusEnum): The new status to set.

    Returns:
        Optional[Conversation]: The updated Conversation object if found and updated, otherwise None.
    """
    try:
        stmt = (
            update(Conversation)
            .where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.account_id == account_id,
                )
            )
            .values(status=new_status, updated_at=func.now())
            .returning(Conversation)
        )
        result = await db.execute(stmt)
        updated_conversation = result.scalar_one_or_none()

        if updated_conversation:
            logger.info(
                f"Updated conversation {conversation_id} status to {new_status}"
            )
            return updated_conversation
        else:
            logger.warning(
                f"Conversation {conversation_id} not found for status update."
            )
            return None

    except SQLAlchemyError as e:
        logger.error(
            f"Database error updating conversation {conversation_id} status: {e}"
        )
        return None


async def increment_conversation_unread_count(
    db: AsyncSession, *, account_id: UUID, conversation_id: UUID, increment_by: int = 1
) -> Optional[Conversation]:
    """Atomically increment the unread_agent_count for a conversation.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        account_id (UUID): The account ID.
        conversation_id (UUID): The conversation ID.
        increment_by (int, optional): Amount to increment (default: 1).

    Returns:
        Optional[Conversation]: The updated Conversation object if found, otherwise None.
    """
    if increment_by <= 0:
        logger.warning("Increment value must be positive.")
        result = await db.execute(select(Conversation).filter_by(id=conversation_id))
        return result.scalar_one_or_none()

    try:
        stmt = (
            update(Conversation)
            .where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.account_id == account_id,
                )
            )
            .values(
                unread_agent_count=Conversation.unread_agent_count + increment_by,
                updated_at=func.now(),
            )
            .returning(Conversation)
            .execution_options(synchronize_session="fetch")
        )
        result = await db.execute(stmt)
        updated_conversation = result.scalar_one_or_none()

        if updated_conversation:
            logger.info(
                f"Incremented unread count for conversation {conversation_id} by {increment_by}"
            )
            return updated_conversation
        else:
            logger.warning(
                f"Conversation {conversation_id} not found for unread count increment."
            )
            return None

    except SQLAlchemyError as e:
        logger.error(
            f"Database error incrementing unread count for {conversation_id}: {e}"
        )
        return None


async def reset_conversation_unread_count(
    db: AsyncSession, *, account_id: UUID, conversation_id: UUID
) -> Optional[Conversation]:
    """Reset the unread_agent_count for a conversation to zero.

    Args:
        db (AsyncSession): SQLAlchemy asynchronous session.
        account_id (UUID): The account ID.
        conversation_id (UUID): The conversation ID.

    Returns:
        Optional[Conversation]: The updated Conversation object if found and updated, otherwise None.
    """
    try:
        stmt = (
            update(Conversation)
            .where(
                and_(
                    Conversation.id == conversation_id,
                    Conversation.account_id == account_id,
                    Conversation.unread_agent_count > 0,
                )
            )
            .values(
                unread_agent_count=0,
                updated_at=func.now(),
            )
            .returning(Conversation)
            .execution_options(synchronize_session="fetch")
        )
        result = await db.execute(stmt)
        updated_conversation = result.scalar_one_or_none()

        if updated_conversation:
            logger.info(f"Reset unread count for conversation {conversation_id}")
            return updated_conversation
        else:
            exists_check = await db.execute(
                select(Conversation.id).filter_by(id=conversation_id)
            )
            if not exists_check.scalar_one_or_none():
                logger.warning(
                    f"Conversation {conversation_id} not found for unread count reset."
                )
            else:
                logger.info(
                    f"Unread count for conversation {conversation_id} was already 0 or reset failed."
                )
                result = await db.execute(
                    select(Conversation).filter_by(id=conversation_id)
                )
                return result.scalar_one_or_none()
            return None

    except SQLAlchemyError as e:
        logger.error(
            f"Database error resetting unread count for {conversation_id}: {e}"
        )
        return None
