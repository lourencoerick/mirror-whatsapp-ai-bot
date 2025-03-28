from uuid import uuid4, UUID
from loguru import logger
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.user import User
from app.models.inbox import Inbox


def setup_initial_data(db: Session):
    logger.info("[onboarding] Starting onboarding setup...")

    account_id = UUID("11111111-1111-1111-1111-111111111111")
    user_id = UUID("22222222-2222-2222-2222-222222222222")
    inbox_id = UUID("33333333-3333-3333-3333-333333333333")
    logger.info(f"Account id: {account_id}\nUser ID: {user_id}\nInbox ID: {inbox_id}")
    account = Account(id=account_id, name="Demo Account", locale="pt-BR")
    db.merge(account)

    user = User(
        id=user_id,
        name="Bot User",
        provider="internal",
        uid=uuid4(),
        encrypted_password="secret",
        sign_in_count=0,
    )
    db.merge(user)

    inbox = Inbox(
        id=inbox_id,
        account_id=account_id,
        channel_id="680df327-c714-40a3-aec5-86ccbb57fa19",
        name="Evolution Inbox",
        channel_type="evolution",
    )
    db.merge(inbox)

    db.commit()
    logger.info("[onboarding] Setup completed successfully.")


if __name__ == "__main__":
    from app.database import SessionLocal

    logger.info("[onboarding] Running onboarding setup from CLI...")
    db: Session = SessionLocal()
    try:
        setup_initial_data(db)
    finally:
        db.close()
