# backend/app/api/schemas/research.py

from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from typing import Optional
from enum import Enum


class ResearchRequest(BaseModel):
    """
    Schema for requesting a new company profile research task.
    Account ID is derived from the authenticated user context.
    """

    url: HttpUrl = Field(..., description="The URL of the company website to research.")

    model_config = {
        "json_schema_extra": {"example": {"url": "https://www.padariadobairro.com.br"}}
    }


class ResearchResponse(BaseModel):
    """
    Schema for the response after successfully enqueueing a research task.
    """

    job_id: Optional[str] = Field(
        None, description="The unique ID assigned to the background job."
    )
    message: str = Field(
        ..., description="Status message indicating the task was queued."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "arq:job:e4r5t6y7-u8i9-0o1p-q2w3-e4r5t6y7u8i9",
                "message": "Company profile research task successfully queued.",
            }
        }
    }


class ResearchJobStatusEnum(str, Enum):
    """Possible statuses for an Arq job."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    NOT_FOUND = "not_found"
    FAILED = "failed"


class ResearchJobStatusResponse(BaseModel):
    """
    Schema for the response when checking the status of a background job.
    """

    job_id: str = Field(..., description="The ID of the job being checked.")
    status: ResearchJobStatusEnum = Field(
        ..., description="The current status of the job."
    )
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
