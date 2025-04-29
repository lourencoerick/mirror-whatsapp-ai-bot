from typing import List, Optional
from uuid import UUID
from loguru import logger
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_document import KnowledgeDocument, DocumentStatus
from app.api.schemas.knowledge_document import KnowledgeDocumentCreate


async def create_document(
    db: AsyncSession,
    *,
    account_id: UUID,
    document_in: KnowledgeDocumentCreate,
    initial_status: DocumentStatus = DocumentStatus.PENDING,
) -> KnowledgeDocument:
    """
    Create a new knowledge document record in the database using a Pydantic schema.

    Args:
        db: The SQLAlchemy AsyncSession.
        account_id: The UUID of the account to which the document belongs.
        document_in: Pydantic schema with document data
                     (source_type, source_uri, original_filename).
        initial_status: The initial status for the document (default: PENDING).

    Returns:
        The newly created KnowledgeDocument instance.
    """
    logger.info(
        f"Creating document for account {account_id}, source: {document_in.source_uri}"
    )
    data = document_in.model_dump(exclude_unset=True)
    db_doc = KnowledgeDocument(
        **data,
        account_id=account_id,
        status=initial_status,
        error_message=None,
        chunk_count=None,
    )
    try:
        db.add(db_doc)
        await db.flush()
        await db.refresh(db_doc)
        logger.success(f"Created KnowledgeDocument id: {db_doc.id}")
        return db_doc
    except Exception:
        logger.exception("Error creating KnowledgeDocument.")
        raise


async def get_document_by_id(
    db: AsyncSession, document_id: UUID
) -> Optional[KnowledgeDocument]:
    """
    Retrieve a knowledge document by its ID.

    Args:
        db: The SQLAlchemy AsyncSession.
        document_id: The UUID of the document to retrieve.

    Returns:
        The KnowledgeDocument object if found, otherwise None.
    """
    logger.debug(f"Fetching document with id: {document_id}")
    stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalars().first()
    if doc:
        logger.debug(f"Found document: {doc.source_uri}")
    else:
        logger.warning(f"Document {document_id} not found.")
    return doc


async def list_documents_by_account(
    db: AsyncSession, account_id: UUID, skip: int = 0, limit: int = 100
) -> List[KnowledgeDocument]:
    """
    List knowledge documents for a specific account with pagination.

    Args:
        db: The SQLAlchemy AsyncSession.
        account_id: The UUID of the account.
        skip: Number of records to skip (pagination offset).
        limit: Maximum number of records to return.

    Returns:
        A list of KnowledgeDocument objects.
    """
    logger.debug(
        f"Listing documents for account {account_id} (skip={skip}, limit={limit})"
    )
    stmt = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.account_id == account_id)
        .order_by(KnowledgeDocument.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    logger.debug(f"Retrieved {len(docs)} documents for account {account_id}.")
    return docs


async def update_document_status(
    db: AsyncSession,
    document_id: UUID,
    status: DocumentStatus,
    error_message: Optional[str] = None,
) -> Optional[KnowledgeDocument]:
    """
    Update the status and optional error message of a knowledge document.

    Args:
        db: The SQLAlchemy AsyncSession.
        document_id: The UUID of the document to update.
        status: The new DocumentStatus.
        error_message: Optional error message (cleared if status is not FAILED).

    Returns:
        The updated KnowledgeDocument object, or None if not found.
    """
    logger.info(f"Updating document {document_id} status to {status.value}")
    values = {
        "status": status,
        "error_message": error_message if status == DocumentStatus.FAILED else None,
    }
    stmt = (
        update(KnowledgeDocument)
        .where(KnowledgeDocument.id == document_id)
        .values(**values)
        .returning(KnowledgeDocument)
    )
    try:
        result = await db.execute(stmt)
        updated = result.scalars().first()
        if updated:
            await db.flush()
        else:
            logger.warning(f"Document {document_id} not found.")
        return updated
    except Exception:
        logger.exception("Error updating document status.")
        raise


async def update_document_chunk_count(
    db: AsyncSession, document_id: UUID, count: int
) -> Optional[KnowledgeDocument]:
    """
    Update the chunk count for a knowledge document.

    Args:
        db: The SQLAlchemy AsyncSession.
        document_id: The UUID of the document to update.
        count: The number of chunks generated.

    Returns:
        The updated KnowledgeDocument object, or None if not found.
    """
    logger.info(f"Setting chunk count for document {document_id} to {count}")
    stmt = (
        update(KnowledgeDocument)
        .where(KnowledgeDocument.id == document_id)
        .values(chunk_count=count)
        .returning(KnowledgeDocument)
    )
    try:
        result = await db.execute(stmt)
        updated = result.scalars().first()
        if updated:
            await db.flush()
        else:
            logger.warning(f"Document {document_id} not found.")
        return updated
    except Exception:
        logger.exception("Error updating chunk count.")
        raise


async def delete_document(db: AsyncSession, document_id: UUID) -> bool:
    """
    Delete a knowledge document and its associated chunks (cascade).

    Args:
        db: The SQLAlchemy AsyncSession.
        document_id: The UUID of the document to delete.

    Returns:
        True if deletion was successful (or document didn't exist), False otherwise.
    """
    logger.warning(f"Attempting to delete document {document_id}")
    doc = await get_document_by_id(db, document_id)
    if not doc:
        logger.warning(f"Document {document_id} not found; nothing to delete.")
        return True
    try:
        await db.delete(doc)
        await db.flush()
        logger.success(f"Deleted document {document_id}.")
        return True
    except Exception:
        logger.exception("Error deleting document.")
        raise


async def count_documents(
    db: AsyncSession, account_id: UUID, search: Optional[str] = None
) -> int:
    """Count the documents matching an optional search filter.

    Args:
        db: The asynchronous database session.
        account_id: The account UUID owning the documents.
        search: An optional search term to filter by name.

    Returns:
        The total count of active contacts.
    """
    stmt = select(func.count(KnowledgeDocument.id)).where(
        KnowledgeDocument.account_id == account_id
    )

    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            KnowledgeDocument.name.ilike(search_term),
        )

    total = await db.scalar(stmt)
    return total or 0
