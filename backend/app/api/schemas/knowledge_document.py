from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from enum import Enum


try:
    from app.models.knowledge_document import DocumentStatus
except ImportError:
    from enum import Enum

    class DocumentStatus(str, Enum):
        PENDING = "pending"
        PROCESSING = "processing"
        COMPLETED = "completed"
        FAILED = "failed"


# --- Schema Base ---
class KnowledgeDocumentBase(BaseModel):
    source_type: str = Field(
        ...,
        description="Type of the source ('file', 'url', 'text').",
        examples=["file", "url"],
    )
    source_uri: str = Field(
        ...,
        description="URI identifying the source (e.g., GCS path, web URL, text description).",
        examples=["gs://my-bucket/report.pdf", "https://company.com/faq"],
    )
    original_filename: Optional[str] = Field(
        None,
        description="Original filename if source_type is 'file'.",
        examples=["report.pdf"],
    )


class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    pass


class KnowledgeDocumentUpdate(BaseModel):
    pass


class KnowledgeDocumentRead(KnowledgeDocumentBase):
    id: UUID = Field(..., description="Unique identifier for the knowledge document.")
    account_id: UUID = Field(..., description="The account this document belongs to.")
    status: DocumentStatus = Field(
        ..., description="Processing status of the document."
    )
    error_message: Optional[str] = Field(
        None, description="Error message if processing failed."
    )
    chunk_count: Optional[int] = Field(
        None, description="Number of chunks generated from this document."
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the document record was created."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the document record was last updated."
    )

    # Habilitar modo ORM para criar a partir de objetos SQLAlchemy
    class Config:
        from_attributes = True


class KnowledgeDocumentList(BaseModel):
    total: int = Field(
        ..., description="Total number of documents found for the account."
    )
    items: List[KnowledgeDocumentRead] = Field(
        ..., description="List of documents for the current page."
    )


class PaginatedKnowledgeDocumentRead(BaseModel):
    total: int = Field(
        ..., description="Total number of documents found for the account."
    )
    items: List[KnowledgeDocumentRead] = Field(
        ..., description="List of documents for the current page."
    )

    class Config:
        from_attributes = True


# --- Schema to Add knowledge  --
class AddTextRequest(BaseModel):

    content: str = Field(
        ..., min_length=10, description="The text content to be ingested."
    )
    title: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="A short description for this text source.",
    )


class AddUrlRequest(BaseModel):
    url: HttpUrl = Field(..., description="The URL to be scraped and ingested.")
    recursive: Optional[bool] = Field(
        default=False,
        description="Whether to recursively crawl and ingest pages linked from this URL.",
    )


class IngestResponse(BaseModel):
    """Response after successfully queueing any ingestion task."""

    document_id: UUID
    job_id: Optional[str]
    message: str


class JobStatusEnum(str, Enum):
    """Possible statuses for an Arq job."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NOT_FOUND = "not_found"
    FAILED = "failed"


class JobStatusResponse(BaseModel):
    """
    Schema for the response when checking the status of a background job.
    """

    job_id: str = Field(..., description="The ID of the job being checked.")
    status: JobStatusEnum = Field(..., description="The current status of the job.")
    detail: Optional[str] = Field(
        None, description="Additional details, like an error message if the job failed."
    )
    # result: Optional[Any] = Field(None, description="The result of the job, if completed successfully and returns a value.") # Less useful here

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"job_id": "arq:job:xyz", "status": "in_progress", "detail": None},
                {
                    "job_id": "arq:job:abc",
                    "status": "complete",
                    "detail": "Profile updated successfully.",
                },
                {
                    "job_id": "arq:job:123",
                    "status": "failed",
                    "detail": "ValueError: Worker context missing essential dependencies.",
                },
                {
                    "job_id": "arq:job:invalid",
                    "status": "not_found",
                    "detail": "Job ID not found in the queue system.",
                },
            ]
        }
    }
