# backend/app/models/api_key.py

import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, JSON, text, sql
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel  # Assuming your custom BaseModel is here


class ApiKey(BaseModel):
    """
    SQLAlchemy model for storing hashed API keys for external integrations.

    Each key is linked to a specific Inbox and has a set of scopes
    that define its permissions.
    """

    __tablename__ = "api_keys"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        doc="Unique identifier for the API key record.",
    )
    name = Column(
        String,
        nullable=False,
        doc="A user-friendly name to identify the key's purpose.",
    )
    hashed_key = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
        doc="The SHA-256 hash of the raw API key.",
    )
    prefix = Column(
        String,
        nullable=False,
        index=True,
        doc="A non-secret prefix to identify the key type (e.g., 'sk_sheets').",
    )
    scopes = Column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
        doc="A list of permission scopes for this key (e.g., ['sheets:trigger']).",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=sql.true(),
        doc="Indicates if the API key is currently active and can be used.",
    )

    # Foreign Key to link the key to an Inbox
    inbox_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("inboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship to the Inbox model
    inbox = relationship("Inbox", back_populates="api_keys")

    def __repr__(self):
        return (
            f"<ApiKey(id={self.id}, prefix='{self.prefix}', inbox_id={self.inbox_id})>"
        )
