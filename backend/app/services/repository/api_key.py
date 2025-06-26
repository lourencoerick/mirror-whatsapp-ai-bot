# backend/app/services/repository/api_key.py

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from loguru import logger
from uuid import UUID

from app.models import ApiKey, Inbox
from app.api.schemas.api_key import ApiKeyCreate
from app.services.api_key import key_service


async def find_api_key_by_hashed_key(
    db: AsyncSession, *, hashed_key: str
) -> Optional[ApiKey]:
    """Finds an API key by its SHA-256 hash.

    This function also eagerly loads the related Inbox and its CompanyProfile
    to prevent additional database queries later in the request lifecycle.

    Args:
        db: The asynchronous database session.
        hashed_key: The hashed API key to search for.

    Returns:
        The ApiKey object if found, otherwise None.
    """
    logger.debug(f"Querying for API key with hash starting with: {hashed_key[:8]}...")

    stmt = (
        select(ApiKey)
        .options(joinedload(ApiKey.inbox).joinedload(Inbox.company_profile))
        .where(ApiKey.hashed_key == hashed_key)
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key:
        logger.debug(f"Found active API key {api_key.id} for Inbox {api_key.inbox_id}")

    return api_key


async def create_api_key_for_inbox(
    db: AsyncSession, *, inbox: Inbox, key_data: ApiKeyCreate
) -> (ApiKey, str):
    """Creates a new API key for a given inbox.

    Args:
        db: The database session.
        inbox: The Inbox object to associate the key with.
        key_data: The data for the new key (name, scopes).

    Returns:
        A tuple containing the saved ApiKey object and the raw, unhashed key.
    """
    prefix = "sk_sheets"  # We can make this dynamic later if needed
    raw_key = key_service.generate_api_key(prefix=prefix)
    hashed_key = key_service.hash_api_key(raw_key)

    new_api_key = ApiKey(
        name=key_data.name,
        hashed_key=hashed_key,
        prefix=prefix,
        scopes=key_data.scopes,
        inbox_id=inbox.id,
    )
    db.add(new_api_key)
    await db.commit()
    await db.refresh(new_api_key)

    logger.info(f"Created new API key {new_api_key.id} for Inbox {inbox.id}")
    return new_api_key, raw_key


async def get_api_keys_for_inbox(db: AsyncSession, *, inbox_id: UUID) -> List[ApiKey]:
    """Retrieves all API keys for a specific inbox."""
    stmt = (
        select(ApiKey)
        .where(ApiKey.inbox_id == inbox_id)
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def delete_api_key(db: AsyncSession, *, api_key: ApiKey) -> bool:
    """Deletes an API key from the database."""
    await db.delete(api_key)
    await db.commit()
    logger.info(f"Deleted API key {api_key.id}")
    return True
