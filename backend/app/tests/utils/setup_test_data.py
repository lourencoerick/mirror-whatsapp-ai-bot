from sqlalchemy.orm import Session
from app.database import SessionLocal

# ⛔️ Remova os imports diretos que causam conflito


def setup_test_data(db: Session):
    from app.models.account_models import Account
    from app.models.inbox_models import Inbox
    from app.models.contact_models import Contact
    from app.models.conversation_models import Conversation
    from app.models.auth_models import User
    from app.models.message_models import Message

    print("Hello from setup_test_data.py")

    # Create account
    account = Account(id=1, name="Test Account")
    db.merge(account)

    # Create user
    user = User(
        id=1,
        name="Test User",
        provider="1",
        uid="1",
        encrypted_password="1",
        sign_in_count=1,
    )
    db.merge(user)

    # Create inbox
    inbox = Inbox(id=1, name="Test Inbox", account_id=1, channel_id=1)
    db.merge(inbox)

    # Create contact 1
    contact1 = Contact(id=1, account_id=1)
    db.merge(contact1)

    # Create contact 2
    contact1 = Contact(id=2, account_id=1)
    db.merge(contact1)

    # Create conversation
    conversation = Conversation(
        id=1,
        account_id=1,
        inbox_id=1,
        status=0,
        display_id=1,
        contact_id=1,
        contact_inbox_id=None,
    )
    db.merge(conversation)

    db.commit()


if __name__ == "__main__":
    db: Session = SessionLocal()
    setup_test_data(db=db)
