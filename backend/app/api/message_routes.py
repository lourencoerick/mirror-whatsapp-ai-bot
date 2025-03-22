from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.schemas.message_schema import MessageCreate
from app.services.logging.message_logger import log_message

router = APIRouter()


@router.post("/messages", status_code=status.HTTP_201_CREATED)
def create_message(payload: MessageCreate, db: Session = Depends(get_db)):
    """
    Create a new message record (incoming or outgoing).

    Can be used by internal components (webhook, bots) or external clients.

    Args:
        payload (MessageCreate): Message details including direction, account context, and content.
        db (Session): Injected database session.

    Returns:
        dict: The ID of the newly created message.
    """
    message = log_message(
        db=db,
        content=payload.content,
        direction=payload.direction,
        account_id=payload.account_id,
        inbox_id=payload.inbox_id,
        conversation_id=payload.conversation_id,
        contact_id=payload.contact_id,
        user_id=payload.user_id,
        source_id=payload.source_id,
        status=payload.status,
        content_attributes=payload.content_attributes,
        content_type=payload.content_type,
        private=int(payload.private) if payload.private is not None else None,
    )

    if not message:
        raise HTTPException(status_code=500, detail="Failed to log message")

    return {"message_id": message.id}
