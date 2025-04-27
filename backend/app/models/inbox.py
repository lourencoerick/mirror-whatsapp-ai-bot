import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.mutable import MutableDict

from sqlalchemy import (
    Column,
    String,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.conversation import ConversationStatusEnum


class Inbox(BaseModel):
    __tablename__ = "inboxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    __table_args__ = (
        Index("inboxes_account_id_index", "account_id"),
        UniqueConstraint(
            "account_id",
            "channel_id",
            "channel_type",
            name="account_inbox_account_id_channel_id_channe_type_unique",
        ),
    )

    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    channel_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    channel_type = Column(String(255), nullable=False)
    initial_conversation_status = Column(
        SQLEnum(
            ConversationStatusEnum, name="conversation_status_enum", create_type=True
        ),
        default=ConversationStatusEnum.PENDING,
        nullable=True,
        comment="Initial status of the conversation when created",
    )
    enable_auto_assignment = Column(Boolean, nullable=True)
    channel_details = Column(MutableDict.as_mutable(JSON), nullable=True, default=dict)

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
    bot_agent_inboxes = relationship(
        "BotAgentInbox", back_populates="inbox", cascade="all, delete-orphan"
    )
    webhooks = relationship(
        "Webhook", back_populates="inbox", cascade="all, delete-orphan"
    )
    events = relationship("Event", back_populates="inbox", cascade="all, delete-orphan")
