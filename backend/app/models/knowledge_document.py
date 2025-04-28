import uuid
from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    DateTime,
    Integer,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from typing import Optional

from app.models.base import BaseModel


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeDocument(BaseModel):
    """
    SQLAlchemy model representing an original source document uploaded
    or linked for the knowledge base.
    """

    __tablename__ = "knowledge_documents"

    id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the knowledge document.",
    )
    account_id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="The account this document belongs to.",
    )
    source_type: str = Column(
        String,
        nullable=False,
        index=True,
        doc="Type of the source ('file', 'url', 'text').",
    )
    # For 'file', stores the key/path in the bucket. For 'url', the URL. For 'text', can be a descriptive name.
    source_uri: str = Column(
        String,
        nullable=False,
        doc="URI identifying the source (e.g., GCS path, web URL, text description).",
    )
    original_filename: Optional[str] = Column(
        String, nullable=True, doc="Original filename for source_type 'file'."
    )
    status: DocumentStatus = Column(
        SAEnum(DocumentStatus, name="document_status_enum", create_type=True),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
        doc="Processing status of the document.",
    )
    error_message: Optional[str] = Column(
        String, nullable=True, doc="Error message if processing failed."
    )
    chunk_count: Optional[int] = Column(
        Integer,
        nullable=True,
        doc="Number of chunks generated from this document.",
    )

    account = relationship("Account", back_populates="knowledge_documents")

    # Relationship with KnowledgeChunk (one document has many chunks). cascade='all, delete-orphan' ensures chunks are deleted if the document is deleted.
    chunks = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select",  # Or 'joined'/'subquery' depending on needs
    )

    def __repr__(self):
        return f"<KnowledgeDocument(id={self.id}, account_id={self.account_id}, source='{self.source_uri}', status='{self.status}')>"
