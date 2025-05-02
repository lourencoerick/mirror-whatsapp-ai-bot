from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def reset_checkpoint(
    db: AsyncSession,
    thread_id: str,
):
    """
    Helper function to reset the checkpoint given a thread_id

    Args:
        db (AsyncSession): Assync Database Session
        thread_id (str): Thread ID of the checkpoints table
    """
    checkpoint_tables = [
        "checkpoint_writes",
        "checkpoint_blobs",
        "checkpoints",
    ]
    logger.info(
        f"[reset_checkpoint] Deleting checkpoint data for thread_id: {thread_id}..."
    )
    for table in checkpoint_tables:
        logger.debug(f"[reset_checkpoint] Deleting from {table}...")
        stmt = text(f"DELETE FROM {table} WHERE thread_id = :thread_id")
        await db.execute(stmt, {"thread_id": thread_id})
        logger.debug(f"[reset_checkpoint] Deleted rows from {table} (if any existed).")
