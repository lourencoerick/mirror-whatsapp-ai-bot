from uuid import UUID
from pydantic import BaseModel


class InboxResponse(BaseModel):
    id: UUID
    name: str
    channel_type: str
