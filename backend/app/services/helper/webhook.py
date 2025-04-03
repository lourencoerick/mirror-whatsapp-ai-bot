from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def find_account_id_from_source(source_id: str, db: AsyncSession) -> UUID | None:
    """Find the account ID associated with a source ID.

    Args:
        source_id (str): The source ID to look up.
        db (AsyncSession): The database session.

    Returns:
        UUID | None: The account ID if found, otherwise None.
    """
    result = await db.execute(
        text("SELECT account_id FROM inboxes WHERE channel_id = :source_id LIMIT 1"),
        {"source_id": source_id},
    )
    row = result.fetchone()
    return row[0] if row else None
