from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.middleware.account_context import get_account_id
from app.api.schemas.message import MessageRead
from app.services.repository.message import find_messages_by_conversation

router = APIRouter()


@router.get(
    "/conversations/{conversation_id}/messages", response_model=List[MessageRead]
)
def get_messages(
    conversation_id: int,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    Retrieve a paginated list of messages from a conversation.

    Args:
        conversation_id (int): ID of the conversation.
        limit (int): Max number of messages to return (default: 20).
        offset (int): Number of messages to skip for pagination (default: 0).
        db (Session): Injected database session.

    Returns:
        List[MessageRead]: List of messages for the given conversation.
    """
    account_id = get_account_id()
    return find_messages_by_conversation(
        db=db,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
        account_id=account_id,
    )
