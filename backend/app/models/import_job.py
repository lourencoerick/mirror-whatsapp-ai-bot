import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    JSON,
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
import enum


from app.models.base import BaseModel


# Define an Enum for the status field for clarity and consistency
class ImportJobStatus(str, enum.Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETE = "Complete"
    FAILED = "Failed"


class ImportJob(BaseModel):
    """
    Represents a background job for importing contacts from a file.
    Tracks the status and results of the import process.
    """

    __tablename__ = "import_jobs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    arq_task_id = Column(
        String, nullable=True, index=True, comment="ID returned by ARQ upon enqueueing"
    )

    status = Column(
        SQLAlchemyEnum(ImportJobStatus, name="import_job_status_enum"),
        nullable=False,
        default=ImportJobStatus.PENDING,
        index=True,
    )

    # Store the key/path to the uploaded file (e.g., S3 key or temp file path)
    file_key = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)

    # Store the result summary as JSON when the job finishes
    result_summary = Column(JSON, nullable=True)
    # Timestamp when processing started (set by the worker)
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    # Timestamp when the job finished (successfully or failed)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    # Define relationship back to Account (optional but good practice)
    account = relationship("Account")  # Assuming Account model exists

    def __repr__(self):
        return f"<ImportJob(id={self.id}, account_id={self.account_id}, status='{self.status}')>"
