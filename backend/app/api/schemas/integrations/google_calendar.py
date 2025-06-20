from pydantic import BaseModel
from typing import Optional, List, Dict


class CalendarResponse(BaseModel):
    """Schema for a single calendar entry in the list response."""

    id: str
    summary: str


class GoogleIntegrationStatus(BaseModel):
    is_connected: bool
    has_all_permissions: bool
    calendars: Optional[List[Dict[str, str]]] = None
    error_message: Optional[str] = None
