from uuid import UUID
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, select
from typing import Optional, List
from loguru import logger
from app.models.conversation import Conversation
from app.models.contact_inbox import ContactInbox
from app.models.inbox_member import InboxMember


def find_by_id(
    db: Session, conversation_id: UUID, account_id: UUID
) -> Optional[Conversation]:
    """
    Retrieves a conversation by ID.
    """
    conversation = (
        db.query(Conversation)
        .filter_by(id=conversation_id, account_id=account_id)
        .first()
    )

    if conversation:
        logger.debug(f"[conversation] Found conversation {conversation.id}")
    else:
        logger.warning(f"[conversation] Not found: {conversation_id}")

    return conversation


def find_conversations_by_inbox(
    db: Session,
    inbox_id: UUID,
    account_id: UUID,
    limit: int = 20,
    offset: int = 0,
) -> List[Conversation]:
    """
    Retrieve a list of conversations for a specific inbox.

    Conversations are ordered by the timestamp of the last message
    in descending order, returning the most recent ones first.

    Args:
        db (Session): The database session.
        inbox_id (UUID): The identifier for the inbox.
        limit (int, optional): The maximum number of records to return (default is 20).
        offset (int, optional): The number of records to skip for pagination (default is 0).
        account_id (UUID): The account identifier

    Returns:
        List[Conversation]: A list of Conversation objects.

    Raises:
        ValueError: If the account ID cannot be determined.
        SQLAlchemyError: If an error occurs during the database query.
    """
    try:
        # Raise an error if account_id remains None after retrieval
        if account_id is None:
            raise ValueError("Account ID could not be determined.")

        query = (
            db.query(Conversation)
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
        return query.all()
    except SQLAlchemyError as e:
        logger.error(f"Database query error: {e}")
        raise e


def find_conversation(
    db: Session,
    inbox_id: int,
    contact_inbox_id: int,
    account_id: Optional[int] = None,
) -> Optional[Conversation]:
    """
    Retrieve a conversation for a contact within an inbox and account.
    """
    if not all([account_id, inbox_id, contact_inbox_id]):
        logger.warning("[conversation] Missing required parameters for lookup")
        return None

    conversation = (
        db.query(Conversation)
        .filter_by(
            account_id=account_id,
            inbox_id=inbox_id,
            contact_inbox_id=contact_inbox_id,
        )
        .first()
    )

    if conversation:
        logger.debug(f"[conversation] Found conversation (id={conversation.id})")
    else:
        logger.info(
            f"[conversation] No conversation found for contact_inbox_id {contact_inbox_id}"
        )

    return conversation


def get_or_create_conversation(
    db: Session,
    inbox_id: UUID,
    account_id: UUID,
    contact_inbox_id: UUID,
) -> Conversation:
    """
    Find or create a conversation for a given contact in an inbox.
    """
    conversation = find_conversation(
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

    contact_inbox: ContactInbox = (
        db.query(ContactInbox)
        .options(joinedload(ContactInbox.contact))
        .filter_by(
            id=contact_inbox_id,
        )
        .first()
    )

    additional_attributes: dict = {}
    additional_attributes["contact_name"] = contact_inbox.contact.name
    additional_attributes["phone_number"] = contact_inbox.contact.phone_number

    conversation = Conversation(
        account_id=account_id,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        status="open",
        additional_attributes=additional_attributes,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.debug(f"[conversation] Created conversation (id={conversation.id})")
    return conversation


def find_all_by_user(
    db: Session,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    account_id: Optional[UUID] = None,
) -> List[Conversation]:
    """
    Retrieve all conversations accessible to a given user based on inbox membership.

    Args:
        db (Session): SQLAlchemy DB session
        user_id (UUID): The user ID
        limit (int): Pagination limit
        offset (int): Pagination offset

    Returns:
        List[Conversation]: Conversations accessible to the user
    """
    inbox_ids_query = select(InboxMember.inbox_id).filter(
        InboxMember.user_id == user_id
    )

    conversations = (
        db.query(Conversation)
        .options(joinedload(Conversation.contact_inbox))
        .filter(Conversation.inbox_id.in_(inbox_ids_query))
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return conversations
