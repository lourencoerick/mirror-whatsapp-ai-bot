from typing import List, Optional, Dict, Any, Union, Tuple
from uuid import UUID
import numpy as np
from loguru import logger
from sqlalchemy import select, delete, tuple_, and_
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
            for k in [
                "chunk_text",
                "chunk_index",
                "embedding",
                "source_type",
                "source_identifier",
            ]
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
                    chunk_index=data["chunk_index"],
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


async def search_similar_chunks_with_context(
    db: AsyncSession,
    account_id: UUID,
    query_embedding: Union[List[float], np.ndarray],
    limit: int = 3,
    similarity_threshold: Optional[float] = None,
) -> Tuple[List[KnowledgeChunk], List[KnowledgeChunk]]:
    """Finds similar chunks and their context, returning both in one call.

    This function finds the top `limit` "seed" chunks and their neighbors.
    It returns a tuple containing:
    1. A list of all unique chunks (seeds + context), sorted by relevance.
    2. The original list of seed chunks.

    Args:
        db: The SQLAlchemy AsyncSession.
        account_id: The UUID of the account to search within.
        query_embedding: The vector embedding of the user's query.
        limit: The number of initial "seed" chunks to find.
        similarity_threshold: An optional cosine similarity threshold.

    Returns:
        A tuple: (all_retrieved_chunks, seed_chunks). Returns ([], []) if
        no chunks are found.
    """
    # Step 1: Find the seed chunks. This is the only vector search call.
    seed_chunks = await search_similar_chunks(
        db,
        account_id=account_id,
        query_embedding=query_embedding,
        limit=limit,
        similarity_threshold=similarity_threshold,
    )

    if not seed_chunks:
        logger.info("No relevant chunks found meeting the similarity criteria.")
        return [], []

    logger.info(f"Found {len(seed_chunks)} initial seed chunks.")

    # Step 2: Map each target chunk to its best relevance rank.
    target_chunks_with_rank = {}
    chunks_without_context = []

    for rank, chunk in enumerate(seed_chunks):
        if chunk.document_id and chunk.source_identifier:
            doc_id = chunk.document_id
            src_id = chunk.source_identifier
            main_index = chunk.chunk_index

            indices_to_check = {main_index, main_index - 1, main_index + 1}

            for index in indices_to_check:
                if index < 0:
                    continue

                key = (doc_id, src_id, index)
                if (
                    key not in target_chunks_with_rank
                    or rank < target_chunks_with_rank[key]
                ):
                    target_chunks_with_rank[key] = rank
        else:
            chunks_without_context.append(chunk)

    all_retrieved_chunks = []
    if target_chunks_with_rank:
        target_identifiers = list(target_chunks_with_rank.keys())

        # Step 3: Fetch all unique target chunks in a single non-vector query.
        stmt = select(KnowledgeChunk).where(
            tuple_(
                KnowledgeChunk.document_id,
                KnowledgeChunk.source_identifier,
                KnowledgeChunk.chunk_index,
            ).in_(target_identifiers)
        )
        result = await db.execute(stmt)
        db_chunks = result.scalars().all()
        all_retrieved_chunks.extend(db_chunks)

    all_retrieved_chunks.extend(chunks_without_context)

    # Step 4: Sort using the hybrid key for relevance.
    def sort_key(c: KnowledgeChunk):
        key = (c.document_id, c.source_identifier, c.chunk_index)
        relevance_rank = target_chunks_with_rank.get(key, float("inf"))
        return (relevance_rank, c.chunk_index)

    all_retrieved_chunks.sort(key=sort_key)

    logger.success(
        f"Returning {len(all_retrieved_chunks)} context chunks and {len(seed_chunks)} seed chunks."
    )
    # Return both the full context list and the original seed list
    return all_retrieved_chunks, seed_chunks


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
