import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column,
    Text,
    String,
    JSON,
    Boolean,
    ForeignKey,
    Index,
    DateTime,
    text,
    sql,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_account_id_index", "account_id"),
        Index("idx_messages_inbox_id_index", "inbox_id"),
        Index("idx_messages_conversation_id_index", "conversation_id"),
        Index("idx_messages_user_id_index", "user_id"),
        Index("idx_messages_bot_agent_id_index", "bot_agent_id"),
        Index("idx_messages_source_id_index", "source_id"),
        Index("idx_messages_contact_id_index", "contact_id"),
        Index("idx_messages_sent_at_index", "sent_at"),
        Index(
            "ix_messages_content_gin_trgm",
            text("(content) gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    content = Column(Text, nullable=True)
    inbox_id = Column(UUID(as_uuid=True), ForeignKey("inboxes.id"), nullable=False)
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    direction = Column(String(50), nullable=False)  # e.g., "in", "out"
    private = Column(Boolean, nullable=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    bot_agent_id = Column(
        UUID(as_uuid=True), ForeignKey("bot_agents.id"), nullable=True
    )

    status = Column(String(50), nullable=True)  # e.g., "received", "processed"
    source_id = Column(String(255), nullable=True)
    content_type = Column(String(50), nullable=True)  # e.g., "text", "image"
    content_attributes = Column(JSON, nullable=True)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )

    is_simulation = Column(
        Boolean, nullable=False, default=False, server_default=sql.false(), index=True
    )
    account = relationship("Account", back_populates="messages")
    inbox = relationship("Inbox", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages", foreign_keys=[user_id])
    bot_agent = relationship(
        "BotAgent", back_populates="messages", foreign_keys=[bot_agent_id]
    )
    contact = relationship("Contact", back_populates="messages")
