# backend/app/api/schemas/research.py

from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from typing import Optional


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
