from pydantic import BaseModel


class CalendarResponse(BaseModel):
    """Schema for a single calendar entry in the list response."""

    id: str
    summary: str
