import pytest
from uuid import uuid4, UUID
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Any, Dict

from app.models.base import Base
from app.models.account import Account
from app.models.user import User
from app.models.account_user import AccountUser, UserRole
from app.models.inbox import Inbox
from app.models.conversation import Conversation
from app.models.contact_inbox import ContactInbox
from app.models.contact import Contact
from app.models.inbox_member import InboxMember

# Import your FastAPI app and the dependencies to override
from app.main import app
from app.database import get_db  # Your original DB dependency getter
from app.core.dependencies.auth import (
    get_auth_context,
    AuthContext,
)

# --- Database Setup for Testing ---
# Use a separate test database if possible
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost:5432/testdb"
# For simplicity, using in-memory SQLite here, but PostgreSQL is better for real integration tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Apply migrations or create tables for the test DB
Base.metadata.create_all(bind=engine)

INSTANCE_ID = "680df327-c714-40a3-aec5-86ccbb57fa19"


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Pytest fixture for providing a test database session."""
    Base.metadata.create_all(bind=engine)  # Ensure tables are created
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()  # Rollback any changes after test
        db.close()
        Base.metadata.drop_all(bind=engine)  # Clean up tables


# --- Test Data Fixtures ---


@pytest.fixture(scope="function")
def test_account(db_session: Session) -> Account:
    """Fixture to create a test account."""
    account = Account(id=uuid4(), name="Test Account")
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture(scope="function")
def test_clerk_user_id() -> str:
    """Fixture to provide a consistent Clerk User ID (sub) for tests."""
    return f"user_{uuid4().hex}"  # Simulate Clerk's user_... format


@pytest.fixture(scope="function")
def test_user(
    db_session: Session, test_account: Account, test_clerk_user_id: str
) -> User:
    """Fixture to create a test user linked via provider='clerk' and uid."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        provider="clerk",  # Link to Clerk
        uid=test_clerk_user_id,  # Use the simulated Clerk ID
        encrypted_password="clerk_managed",  # Placeholder
        sign_in_count=1,
    )
    account_user = AccountUser(user=user, account=test_account, role=UserRole.ADMIN)
    db_session.add_all([user, account_user])
    db_session.commit()
    db_session.refresh(user)
    # Eager load relationships needed by AuthContext (adjust if needed)
    db_session.refresh(user, attribute_names=["account_users"])
    db_session.refresh(user.account_users[0], attribute_names=["account"])
    return user


@pytest.fixture(scope="function")
def test_inbox(db_session: Session, test_account: Account, test_user: User) -> Inbox:
    """Fixture to create a test inbox."""
    inbox = Inbox(
        id=uuid4(),
        name="Test Inbox",
        account_id=test_account.id,
        channel_type="evolution",
        channel_id=INSTANCE_ID,
    )

    inbox_member = InboxMember(id=uuid4(), user_id=test_user.id, inbox_id=inbox.id)
    db_session.add_all([inbox, inbox_member])

    db_session.add(inbox)
    db_session.commit()
    db_session.refresh(inbox)
    return inbox


# --- Dependency Override Fixture ---


@pytest.fixture(scope="function")
def override_get_auth_context(test_user: User, test_account: Account):
    """Fixture to create the override function for get_auth_context."""

    def _override():
        # Directly return the AuthContext with test data
        # Assumes test_user fixture has loaded necessary relationships
        return AuthContext(internal_user=test_user, active_account=test_account)

    return _override


# --- Test Client Fixture ---


@pytest.fixture(scope="function")
def client(
    db_session: Session, override_get_auth_context: Any
) -> Generator[TestClient, None, None]:
    """Pytest fixture for providing a TestClient with auth context override."""

    def override_get_db() -> Generator[Session, None, None]:
        # Simplesmente retorna a mesma sessão usada no teste
        yield db_session

    # Apply the override
    app.dependency_overrides[get_auth_context] = override_get_auth_context
    app.dependency_overrides[get_db] = override_get_db

    # Provide the client
    with TestClient(app) as test_client:
        yield test_client
    # Clean up the override after the test
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def unauthenticated_client() -> Generator[TestClient, None, None]:
    """Pytest fixture for providing a TestClient WITHOUT auth context override."""
    app.dependency_overrides.clear()  # Ensure no overrides are active
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_evolution_inbox(
    db_session: Session, test_account: Account, test_user: User
) -> Inbox:
    """
    Fixture to create a test Account and an Inbox linked to the specific
    INSTANCE_ID expected by the Evolution webhook payload.
    Depends on db_session and test_account fixtures.
    """
    # Check if an inbox with this channel_id already exists for the account
    existing_inbox = (
        db_session.query(Inbox)
        .filter(
            Inbox.account_id == test_account.id,
            Inbox.channel_id
            == INSTANCE_ID,  # Assuming channel_id stores the instanceId
        )
        .first()
    )

    if existing_inbox:
        # If it exists from a previous (failed?) test run in the same session scope, use it
        # Or handle cleanup better in db_session fixture
        return existing_inbox

    # Create the inbox linked to the test_account and the specific INSTANCE_ID
    inbox = Inbox(
        id=uuid4(),
        name="Evolution Test Inbox",
        account_id=test_account.id,  # Use the account from the fixture
        channel_type="whatsapp",
        channel_id=INSTANCE_ID,  # Store the specific ID the webhook uses
    )

    inbox_member = InboxMember(id=uuid4(), user_id=test_user.id, inbox_id=inbox.id)
    db_session.add_all([inbox, inbox_member])
    db_session.commit()
    db_session.refresh(inbox)
    return inbox


@pytest.fixture
def valid_evolution_payload() -> Dict[str, Any]:
    """Provides a valid sample payload for the Evolution webhook."""
    return {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511941986775@s.whatsapp.net",
                "fromMe": False,
                "id": "wamid.12345",  # This will be the source_id
            },
            "pushName": "LL",
            "message": {"conversation": "Olá, isso é um teste!"},
            "messageType": "conversation",
            "messageTimestamp": 1742771256,
            "instanceId": INSTANCE_ID,  # Match the ID set in test_evolution_inbox
            "source": "ios",
        },
    }
