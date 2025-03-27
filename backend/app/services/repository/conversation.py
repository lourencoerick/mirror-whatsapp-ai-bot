from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc
from typing import Optional, List
from loguru import logger
from app.middleware.account_context import get_account_id
from app.models.conversation import Conversation
from app.models.contact__inbox import ContactInbox


def find_by_id(db: Session, conversation_id: int) -> Optional[Conversation]:
    """
    Retrieves a conversation by ID.
    """
    conversation = db.query(Conversation).filter_by(id=conversation_id).first()

    if conversation:
        logger.debug(f"[conversation] Found conversation {conversation.id}")
    else:
        logger.warning(f"[conversation] Not found: {conversation_id}")

    return conversation


def find_conversations_by_inbox(
    db: Session,
    inbox_id: int,
    limit: int = 20,
    offset: int = 0,
    account_id: Optional[int] = None,
) -> List[Conversation]:
    """
    Retrieve a list of conversations for a specific inbox.

    Conversations are ordered by the timestamp of the last message
    in descending order, returning the most recent ones first.

    Args:
        db (Session): The database session.
        inbox_id (int): The identifier for the inbox.
        limit (int, optional): The maximum number of records to return (default is 20).
        offset (int, optional): The number of records to skip for pagination (default is 0).
        account_id (Optional[int], optional): The account identifier. If not provided,
            it will be retrieved using `get_account_id()`.

    Returns:
        List[Conversation]: A list of Conversation objects.

    Raises:
        ValueError: If the account ID cannot be determined.
        SQLAlchemyError: If an error occurs during the database query.
    """
    try:
        # Retrieve account_id if not provided
        if account_id is None:
            account_id = get_account_id()

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
    inbox_id: int,
    contact_inbox_id: int,
    account_id: Optional[int] = None,
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
    conversation = Conversation(
        account_id=account_id,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox_id,
        status="open",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    logger.debug(f"[conversation] Created conversation (id={conversation.id})")
    return conversation
