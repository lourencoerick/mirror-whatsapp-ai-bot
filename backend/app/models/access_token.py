from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    UniqueConstraint,
    Index,
    Boolean,
)
from app.models.base import BaseModel


class AccessToken(BaseModel):
    __tablename__ = "access_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="access_tokens_token_unique"),
        Index("access_tokens_owner_type_owner_id_index", "owner_type", "owner_id"),
    )
    owner_type = Column(String(255), nullable=True)
    owner_id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    token = Column(String(255), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)
    scopes = Column(String(255), nullable=True)
