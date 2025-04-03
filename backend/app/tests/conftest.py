import asyncio
import os
from uuid import uuid4, UUID
from typing import Any, Dict, AsyncGenerator, Callable

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import select
from datetime import datetime, timezone

# Model and App Imports
from app.models.base import Base
from app.models.account import Account
from app.models.user import User
from app.models.account_user import AccountUser, UserRole
from app.models.inbox import Inbox
from app.models.conversation import Conversation
from app.models.contact_inbox import ContactInbox
from app.models.contact import Contact
from app.models.inbox_member import InboxMember
from app.main import app
from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext


# --- Core Test Setup ---


@pytest.fixture(scope="session")
def event_loop():
    """Provides a session-scoped event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# --- Database Configuration ---

TEST_DB_USER = os.getenv("TEST_DB_USER", "user")
TEST_DB_PASSWORD = os.getenv("TEST_DB_PASSWORD", "password")
TEST_DB_HOST = os.getenv("TEST_DB_HOST", "database")
TEST_DB_PORT = os.getenv("TEST_DB_PORT", "5432")
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "test_chatbotdb")

ASYNC_SQLALCHEMY_DATABASE_URL = (
    f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}@"
    f"{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
)

async_engine = create_async_engine(ASYNC_SQLALCHEMY_DATABASE_URL, echo=False)

AsyncTestingSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# --- Constants ---
INSTANCE_ID = "c844e6dc-b3ab-4456-92f9-7e39d563f43a"


# --- Database Fixtures ---


@pytest_asyncio.fixture(scope="function", autouse=True)
async def prepare_database() -> AsyncGenerator[None, None]:
    """Creates and drops all tables for each test function."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional database session per test."""
    session = AsyncTestingSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# --- Test Data Fixtures ---


@pytest_asyncio.fixture(scope="function")
async def test_account(db_session: AsyncSession) -> Account:
    """Creates and returns a persisted test Account."""
    account = Account(id=uuid4(), name="Test Account")
    db_session.add(account)
    await db_session.flush()
    await db_session.refresh(account)
    return account


@pytest.fixture(scope="function")
def test_clerk_user_id() -> str:
    """Provides a unique Clerk user ID string."""
    return f"user_{uuid4().hex}"


@pytest_asyncio.fixture(scope="function")
async def test_user(
    db_session: AsyncSession, test_account: Account, test_clerk_user_id: str
) -> User:
    """Creates and returns a persisted test User with an Admin role."""
    user = User(
        id=uuid4(),
        name="Test User",
        email="test@example.com",
        provider="clerk",
        uid=test_clerk_user_id,
        encrypted_password="clerk_managed",
        sign_in_count=1,
    )
    account_user = AccountUser(user=user, account=test_account, role=UserRole.ADMIN)
    db_session.add(user)
    db_session.add(account_user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_inbox(
    db_session: AsyncSession, test_account: Account, test_user: User
) -> Inbox:
    """Creates and returns a persisted test Inbox with a member."""
    inbox = Inbox(
        id=uuid4(),
        name="Test Inbox",
        account_id=test_account.id,
        channel_type="evolution",
        channel_id=INSTANCE_ID,
    )
    db_session.add(inbox)
    await db_session.flush()

    inbox_member = InboxMember(id=uuid4(), user_id=test_user.id, inbox_id=inbox.id)
    db_session.add(inbox_member)
    await db_session.flush()
    await db_session.refresh(inbox)
    return inbox


@pytest_asyncio.fixture(scope="function")
async def test_evolution_inbox(
    db_session: AsyncSession, test_account: Account, test_user: User
) -> Inbox:
    """Creates a specific 'Evolution Test Inbox' (whatsapp type)."""
    inbox = Inbox(
        id=uuid4(),
        name="Evolution Test Inbox",
        account_id=test_account.id,
        channel_type="whatsapp",
        channel_id=INSTANCE_ID,
    )
    db_session.add(inbox)
    await db_session.flush()

    inbox_member = InboxMember(id=uuid4(), user_id=test_user.id, inbox_id=inbox.id)
    db_session.add(inbox_member)
    await db_session.flush()
    await db_session.refresh(inbox)
    return inbox


@pytest_asyncio.fixture(scope="function")
async def test_contact(db_session: AsyncSession, test_account: Account) -> Contact:
    """Creates and returns a persisted test Contact."""
    contact = Contact(
        id=uuid4(),
        account_id=test_account.id,
        phone_number="5511941986775",
        name="Test Contact from Fixture",
    )
    db_session.add(contact)
    await db_session.flush()
    await db_session.refresh(contact)
    return contact


# --- Dependency Override Fixtures ---


@pytest.fixture(scope="function")
def override_get_auth_context_factory(
    test_user: User, test_account: Account
) -> Callable[[], AuthContext]:
    """Creates a factory to override `get_auth_context` dependency."""

    def _override() -> AuthContext:
        """Returns AuthContext with test_user and test_account."""
        return AuthContext(internal_user=test_user, active_account=test_account)

    return _override


# --- HTTP Client Fixtures ---


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession,
    override_get_auth_context_factory: Callable[[], AuthContext],
) -> AsyncGenerator[AsyncClient, None]:
    """Provides an authenticated test client with DB and Auth overrides."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_auth_context] = override_get_auth_context_factory
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def unauthenticated_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provides an unauthenticated test client with DB override."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    if get_auth_context in app.dependency_overrides:
        del app.dependency_overrides[get_auth_context]

    async with AsyncClient(app=app, base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.clear()

    # --- Sample Payloads ---


@pytest.fixture
def valid_evolution_payload() -> Dict[str, Any]:
    """Provides a valid sample payload for the Evolution webhook."""
    return {
        "event": "messages.upsert",
        "instance": INSTANCE_ID,
        "data": {
            "key": {
                "remoteJid": "5511941986775@s.whatsapp.net",
                "fromMe": False,
                "id": f"wamid.{uuid4().hex}",
            },
            "pushName": "Test Contact",
            "message": {"conversation": "Olá, isso é um teste de webhook!"},
            "messageType": "conversation",
            "messageTimestamp": 1742771256,
            "instanceId": INSTANCE_ID,
            "source": "ios",
        },
        "destination": "5511941986775",
        "date_time": datetime.now(timezone.utc).isoformat(),
        "server_url": "url_teste",
        "apikey": "api_key",
    }
