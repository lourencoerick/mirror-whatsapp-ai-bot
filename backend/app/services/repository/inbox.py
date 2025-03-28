from uuid import UUID
from sqlalchemy.orm import Session
from typing import Optional
from loguru import logger
from app.models.inbox import Inbox


def find_by_id(
    db: Session, inbox_id: UUID, account_id: Optional[UUID] = None
) -> Optional[Inbox]:

    inbox = db.query(Inbox).filter_by(account_id=account_id, id=inbox_id).first()

    if inbox:
        logger.debug(f"[inbox] Found inbox id={inbox_id})")
    else:
        logger.info(f"[inbox] No inbox found inbox id={inbox_id}")

    return inbox


def find_by_channel_id(
    db: Session, account_id: UUID, channel_id: str
) -> Optional[Inbox]:
    """
    Retrieve an inbox by channel_id and account_id.
    Logs result for traceability.
    """
    if not account_id or not channel_id:
        logger.warning("[inbox] Missing account_id or channel_id")
        return None

    inbox = (
        db.query(Inbox).filter_by(account_id=account_id, channel_id=channel_id).first()
    )

    if inbox:
        logger.debug(f"[inbox] Found inbox (id={inbox.id}) for channel_id {channel_id}")
    else:
        logger.info(
            f"[inbox] No inbox found for channel_id {channel_id} (account_id={account_id})"
        )

    return inbox


def get_or_create_by_channel_id(
    db: Session, account_id: UUID, channel_id: str
) -> Inbox:
    """
    Retrieve or create an inbox using channel_id and account_id.
    Logs both cases.
    """
    inbox = find_by_channel_id(db, account_id, channel_id)
    if inbox:
        return inbox

    logger.info(
        f"[inbox] Creating new inbox for channel_id {channel_id} (account_id={account_id})"
    )

    inbox = Inbox(account_id=account_id, channel_id=channel_id)
    db.add(inbox)
    db.commit()
    db.refresh(inbox)

    logger.debug(f"[inbox] Created inbox (id={inbox.id}) for channel_id {channel_id}")
    return inbox
