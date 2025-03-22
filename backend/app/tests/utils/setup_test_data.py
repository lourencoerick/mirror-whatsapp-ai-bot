from sqlalchemy.orm import Session
from app.models.account_models import Account
from app.models.inbox_models import Inbox
from app.models.contact_models import Contact
from app.models.conversation_models import Conversation
from app.models.auth_models import User


def setup_test_data(db: Session):
    """
    Seed essential records to support Message creation tests.

    This function ensures all foreign key dependencies are resolved before
    message creation. Useful for integration tests or dev bootstrapping.
    """
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

    # Create contact
    contact = Contact(id=1, account_id=1)
    db.merge(contact)

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
