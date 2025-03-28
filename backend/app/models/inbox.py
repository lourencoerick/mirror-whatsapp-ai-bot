import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Inbox(BaseModel):
    __tablename__ = "inboxes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    __table_args__ = (Index("inboxes_account_id_index", "account_id"),)

    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    channel_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    channel_type = Column(String(255), nullable=True)
    enable_auto_assignment = Column(Boolean, nullable=True)

    account = relationship("Account", back_populates="inboxes")
    messages = relationship(
        "Message", back_populates="inbox", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "Conversation", back_populates="inbox", cascade="all, delete-orphan"
    )
    contact_inboxes = relationship(
        "ContactInbox", back_populates="inbox", cascade="all, delete-orphan"
    )
    inbox_members = relationship(
        "InboxMember", back_populates="inbox", cascade="all, delete-orphan"
    )
    agent_bot_inboxes = relationship(
        "AgentBotInbox", back_populates="inbox", cascade="all, delete-orphan"
    )
    webhooks = relationship(
        "Webhook", back_populates="inbox", cascade="all, delete-orphan"
    )
    events = relationship("Event", back_populates="inbox", cascade="all, delete-orphan")
