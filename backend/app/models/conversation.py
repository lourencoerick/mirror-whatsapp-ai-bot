import uuid
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID, JSONB

from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
    Enum as SQLEnum,
    sql,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableDict
import enum

from app.models.base import BaseModel


class ConversationStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    HUMAN_ACTIVE = "HUMAN_ACTIVE"
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    BOT = "BOT"


class Conversation(BaseModel):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_account_id", "account_id"),
        Index("idx_conversations_inbox_id", "inbox_id"),
        Index("idx_conversations_last_message_at", "last_message_at"),
        Index("idx_conversations_contact_inbox_id", "contact_inbox_id"),
        # --- GIN Trigram Index on JSONB Expression for 'contact_name' ---
        Index(
            "ix_conv_addt_attrs_contact_name_gin_trgm",
            text("(additional_attributes->>'contact_name') gin_trgm_ops"),
            postgresql_using="gin",
        ),
        # --- GIN Trigram Index on JSONB Expression for 'phone_number' ---
        Index(
            "ix_conv_addt_attrs_phone_number_gin_trgm",
            text("(additional_attributes->>'phone_number') gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    inbox_id = Column(UUID(as_uuid=True), ForeignKey("inboxes.id"), nullable=False)
    contact_inbox_id = Column(
        UUID(as_uuid=True), ForeignKey("contact_inboxes.id"), nullable=False
    )

    assignee_id = Column(UUID(as_uuid=True), nullable=True)
    display_id = Column(String(255), nullable=True)

    user_last_seen_at = Column(DateTime(timezone=True), nullable=True)
    agent_last_seen_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(
        SQLEnum(
            ConversationStatusEnum, name="conversation_status_enum", create_type=True
        ),
        default=ConversationStatusEnum.PENDING,
        nullable=False,
        index=True,
        comment="Current status of the conversation regarding human interaction",
    )

    unread_agent_count = Column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
        comment="Count of unread messages for the agent since last interaction/read",
    )

    is_bot_active = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    is_simulation = Column(
        Boolean, nullable=False, default=False, server_default=sql.false(), index=True
    )

    locked = Column(Boolean, nullable=True)

    last_message_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    additional_attributes = Column(
        MutableDict.as_mutable(JSONB), default=dict, nullable=True
    )

    ping_pong_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        doc="Counts consecutive agent messages without a significant user delay, to prevent bot loops.",
    )

    last_agent_message_timestamp = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the last message sent by our agent in this conversation.",
    )

    account = relationship(
        "Account",
        back_populates="conversations",
        foreign_keys=[account_id],
    )
    inbox = relationship("Inbox", back_populates="conversations")
    contact_inbox = relationship("ContactInbox", back_populates="conversation")

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="conversation", cascade="all, delete-orphan"
    )
