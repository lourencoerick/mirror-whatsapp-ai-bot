import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Index
from typing import Optional, Dict, Any
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


try:
    from pgvector.sqlalchemy import Vector

    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    print("WARNING: pgvector.sqlalchemy not found. Vector type operations might fail.")

from app.models.base import BaseModel

# Define the embedding dimension (MUST match the migration and the embedding model)
EMBEDDING_DIMENSION = 1536  #  text-embedding-3-small


class KnowledgeChunk(BaseModel):
    """
    SQLAlchemy model for storing text chunks and their vector embeddings.
    Represents a piece of knowledge associated with an account.
    """

    __tablename__ = "knowledge_chunks"

    id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the knowledge chunk.",
    )
    account_id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The account this knowledge chunk belongs to.",
    )

    document_id: Optional[uuid.UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "knowledge_documents.id", ondelete="CASCADE"
        ),  # Delete chunks if the document is deleted
        nullable=True,
        index=True,
        doc="Optional link to the original source document.",
    )

    source_type: str = Column(
        String,
        nullable=False,
        doc="Type of the original source (e.g., 'file', 'url', 'text').",
    )
    source_identifier: str = Column(
        String,
        nullable=False,
        doc="Identifier of the source (e.g., filename, URL, description).",
    )
    chunk_text: str = Column(
        Text, nullable=False, doc="The actual text content of the chunk."
    )

    embedding = Column(
        Vector(EMBEDDING_DIMENSION),  # Specify the dimension
        nullable=False,
        doc=f"Vector embedding of the chunk text (dimension: {EMBEDDING_DIMENSION}).",
    )
    metadata_: Optional[Dict[str, Any]] = Column(
        "metadata",
        JSONB,
        nullable=True,
        doc="Additional metadata associated with the chunk (e.g., page number, source section).",
    )

    account = relationship("Account", back_populates="knowledge_chunks")

    document = relationship("KnowledgeDocument", back_populates="chunks")

    def __repr__(self):
        doc_id_str = f", document_id={self.document_id}" if self.document_id else ""
        return f"<KnowledgeChunk(id={self.id}, account_id={self.account_id}{doc_id_str}, text_len={len(self.chunk_text or '')})>"
