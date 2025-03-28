from uuid import uuid4
from sqlalchemy.orm import Session
from app.database import SessionLocal


def setup_test_data(db: Session):
    from app.models.account import Account
    from app.models.inbox import Inbox
    from app.models.contact import Contact
    from app.models.contact__inbox import ContactInbox
    from app.models.conversation import Conversation
    from app.models.user import User
    from app.models.message import Message

    # Criação de IDs fixos para consistência nos testes
    account_id = uuid4()
    user_id = uuid4()
    inbox_id = uuid4()
    contact_id_1 = uuid4()
    contact_id_2 = uuid4()
    conversation_id = uuid4()

    # Create account
    account = Account(id=account_id, name="Test Account")
    db.merge(account)

    # Create user
    user = User(
        id=user_id,
        name="Test User",
        provider="1",
        uid=uuid4(),
        encrypted_password="1",
        sign_in_count=1,
    )
    db.merge(user)

    # Create inbox
    inbox = Inbox(
        id=inbox_id, name="Test Inbox", account_id=account_id, channel_id="channel-123"
    )
    db.merge(inbox)

    # Create contact 1
    contact1 = Contact(
        id=contact_id_1, account_id=account_id, phone_number="551111111111"
    )
    db.merge(contact1)

    # Create contact 2
    contact2 = Contact(
        id=contact_id_2, account_id=account_id, phone_number="552222222222"
    )
    db.merge(contact2)

    # ContactInbox (ligação entre contact1 e inbox)
    contact_inbox = ContactInbox(
        id=uuid4(), contact_id=contact_id_1, inbox_id=inbox_id, source_id="test-source"
    )
    db.merge(contact_inbox)

    # Create conversation
    conversation = Conversation(
        id=conversation_id,
        account_id=account_id,
        inbox_id=inbox_id,
        contact_inbox_id=contact_inbox.id,
        status="open",
        display_id="conv-001",
    )
    db.merge(conversation)

    db.commit()


if __name__ == "__main__":
    db: Session = SessionLocal()
    setup_test_data(db=db)
