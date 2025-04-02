from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.config import get_settings

settings = get_settings()

DATABASE_URL = settings.DATABASE_URL

async_engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

AsyncSessionLocal = sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)

Base = declarative_base()


@asynccontextmanager
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


def create_db_and_tables():
    """
    Creates the database and tables (synchronously).
    This function is intended for initialization purposes.
    """
    from sqlalchemy import create_engine

    engine = create_engine(
        DATABASE_URL.replace("+asyncpg", "")
    )  # Remova o asyncpg para usar a engine síncrona
    Base.metadata.create_all(engine)
