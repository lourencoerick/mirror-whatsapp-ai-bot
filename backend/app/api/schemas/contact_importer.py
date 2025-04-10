from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from app.models.import_job import ImportJobStatus


class ContactImportError(BaseModel):
    """Details about an error encountered for a specific row during import."""

    row_number: int = Field(
        ..., description="The row number in the CSV file (starting from 2)"
    )
    reason: str = Field(..., description="Description of the error")
    data: Dict[str, Any] = Field(
        ..., description="The data from the row that caused the error"
    )


class ContactImportSummary(BaseModel):
    """Summary of the results after a contact import job is completed."""

    total_rows_processed: int = Field(
        ..., description="Total number of data rows processed in the CSV"
    )
    successful_imports: int = Field(
        ..., description="Number of contacts successfully created or updated"
    )
    failed_imports: int = Field(
        ..., description="Number of rows that failed during import"
    )
    errors: List[ContactImportError] = Field(
        [], description="List of specific errors encountered"
    )


class ContactImportJobStartResponse(BaseModel):
    """Response returned when a contact import job is successfully initiated."""

    id: UUID = Field(
        ...,
        description="The unique identifier for the background import job.",
    )
    status: str = Field(
        "Pending", description="Initial status of the job."
    )  # Or "Queued"

    class Config:
        from_attributes = True


class ContactImportJobStatusResponse(BaseModel):
    """Detailed status and results of a contact import job."""

    id: UUID = Field(..., description="The unique identifier for the import job.")
    status: str = Field(
        ...,
        description="Current status of the job (e.g., PENDING, PROCESSING, COMPLETE, FAILED).",
    )
    file_key: Optional[str] = Field(
        None,
        description="Identifier for the uploaded file in storage (e.g., GCS blob name).",
    )  # Optional: Might not want to expose this
    original_filename: Optional[str] = Field(
        None,
        description="Original name of the uploaded file.",
    )
    created_at: datetime = Field(..., description="Timestamp when the job was created.")
    finished_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the job finished processing (null if not finished).",
    )

    result_summary: Optional[ContactImportSummary] = Field(
        None,
        description="Summary of import results (available when status is COMPLETE or FAILED with partial results).",
    )

    class Config:
        from_attributes = True

        populate_by_name = True


class ImportJobListItem(BaseModel):
    """Data for a single import job item in a list."""

    id: UUID = Field(...)
    status: ImportJobStatus
    original_filename: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedImportJobListResponse(BaseModel):
    """Response model for paginated list of import jobs."""

    total_items: int
    total_pages: int
    page: int
    size: int
    items: List[ImportJobListItem]

    class Config:
        from_attributes = True
