from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import numpy as np
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# Vector support for pgvector-based similarity queries
try:
    from pgvector.sqlalchemy import Vector

    PGVECTOR_AVAILABLE = True
except ImportError:
    logger.error("pgvector.sqlalchemy not found. Similarity queries will fail.")
    PGVECTOR_AVAILABLE = False
    Vector = None  # type: ignore

from app.models.knowledge_chunk import KnowledgeChunk, EMBEDDING_DIMENSION


async def check_knowledge_chunks_exist_for_account(
    db: AsyncSession, account_id: UUID
) -> bool:
    """Checks if any knowledge chunks exist for a given account."""
    stmt = (
        select(KnowledgeChunk.id)
        .where(KnowledgeChunk.account_id == account_id)
        .limit(1)
    )
    result = await db.execute(select(stmt.exists()))
    return result.scalar_one()


async def add_chunks(
    db: AsyncSession,
    account_id: UUID,
    chunks_data: List[Dict[str, Any]],
) -> int:
    """
    Bulk-insert knowledge chunks for an account. Returns the count added.
    """
    if not chunks_data:
        logger.info("No chunks provided.")
        return 0

    new_chunks = []
    for data in chunks_data:
        # Validate required keys and embedding dimension
        if not all(
            k in data
            for k in ["chunk_text", "embedding", "source_type", "source_identifier"]
        ):
            logger.warning("Skipping chunk with missing fields.")
            continue
        if len(data["embedding"]) != EMBEDDING_DIMENSION:
            logger.warning("Skipping chunk with incorrect embedding length.")
            continue

        try:
            new_chunks.append(
                KnowledgeChunk(
                    account_id=account_id,
                    chunk_text=data["chunk_text"],
                    embedding=data["embedding"],
                    source_type=data["source_type"],
                    source_identifier=data["source_identifier"],
                    metadata_=data.get("metadata_"),
                    document_id=data.get("document_id"),
                )
            )
        except Exception as e:
            logger.error(f"Error creating chunk object: {e}")

    if not new_chunks:
        logger.warning("No valid chunks to add.")
        return 0

    try:
        db.add_all(new_chunks)
        await db.flush()
        logger.success(f"Added {len(new_chunks)} chunks for account {account_id}.")
        return len(new_chunks)
    except Exception:
        logger.exception("Database error during bulk insert.")
        raise


async def search_similar_chunks(
    db: AsyncSession,
    account_id: UUID,
    query_embedding: Union[List[float], np.ndarray],
    limit: int = 5,
    similarity_threshold: Optional[float] = None,
) -> List[KnowledgeChunk]:
    """
    Retrieve chunks most similar to the query embedding.
    """
    if not PGVECTOR_AVAILABLE:
        logger.error("pgvector not available.")
        return []
    if len(query_embedding) != EMBEDDING_DIMENSION:
        logger.error("Query embedding dimension mismatch.")
        return []

    try:
        stmt = select(KnowledgeChunk).where(KnowledgeChunk.account_id == account_id)
        distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
        stmt = stmt.order_by(distance.asc())

        if similarity_threshold is not None:
            max_dist = 1.0 - similarity_threshold
            stmt = stmt.where(distance <= max_dist)

        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        chunks = result.scalars().all()
        logger.info(f"Found {len(chunks)} similar chunks.")
        return chunks
    except Exception:
        logger.exception("Error during similarity search.")
        return []


async def delete_chunks_by_document_id(db: AsyncSession, document_id: UUID) -> int:
    """
    Remove all chunks linked to a document. Returns deleted count.
    """
    try:
        stmt = delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        result = await db.execute(stmt)
        await db.flush()
        count = result.rowcount or 0
        logger.info(f"Deleted {count} chunks for document {document_id}.")
        return count
    except Exception:
        logger.exception("Error deleting chunks by document_id.")
        raise
