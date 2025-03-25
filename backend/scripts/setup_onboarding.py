from loguru import logger
from sqlalchemy.orm import Session

from app.models.account_models import Account
from app.models.auth_models import User
from app.models.inbox_models import Inbox
from app.models.contact_models import Contact, ContactInbox
from app.models.conversation_models import Conversation


def setup_initial_data(db: Session):
    logger.info("[onboarding] Starting onboarding setup...")

    account = Account(id=1, name="Demo Account", locale="pt-BR")
    db.merge(account)

    user = User(
        id=1,
        name="Bot User",
        provider="internal",
        uid="bot_user_1",
        encrypted_password="secret",
        sign_in_count=0,
    )
    db.merge(user)

    inbox = Inbox(
        id=1,
        account_id=1,
        channel_id="680df327-c714-40a3-aec5-86ccbb57fa19",
        name="Evolution Inbox",
        channel_type="evolution",
    )
    db.merge(inbox)

    contact = Contact(
        id=1, account_id=1, name="Primeiro Cliente", identifier="5511912345678"
    )
    db.merge(contact)

    contact_inbox = ContactInbox(
        id=1, contact_id=contact.id, inbox_id=inbox.id, source_id="teste"
    )

    db.merge(contact_inbox)

    conversation = Conversation(
        id=1,
        account_id=1,
        inbox_id=1,
        status="open",
        contact_inbox_id=contact_inbox.id,
    )
    db.merge(conversation)

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
