from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.config import get_settings

settings = get_settings()

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

AsyncSessionLocal = sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    Ensures the session is closed after use.

    Yields:
        AsyncSession: SQLAlchemy AsyncSession
    """
    db = AsyncSessionLocal()
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


def create_db_and_tables(url: str):
    """
    Creates the database and tables (synchronously).
    This function is intended for initialization purposes.
    """
    from sqlalchemy import create_engine

    engine = create_engine(
        url.replace("+asyncpg", "")
    )  # Remova o asyncpg para usar a engine síncrona
    Base.metadata.create_all(engine)
