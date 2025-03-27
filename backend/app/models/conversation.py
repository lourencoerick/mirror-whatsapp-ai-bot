from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
    String,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from sqlalchemy.ext.mutable import MutableDict


class Conversation(BaseModel):
    __tablename__ = "conversations"
    __table_args__ = (
        # UniqueConstraint(
        #     "account_id",
        #     "display_id",
        #     name="conversations_account_id_display_id_unique",
        # ),
        Index("conversations_account_id_index", "account_id"),
        Index("conversations_contact_inbox_id_index", "contact_inbox_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=False)
    contact_inbox_id = Column(Integer, ForeignKey("contact_inboxes.id"), nullable=False)

    status = Column(String(50), nullable=False)
    assignee_id = Column(Integer, nullable=True)
    display_id = Column(Integer, nullable=True)

    user_last_seen_at = Column(DateTime, nullable=True)
    agent_last_seen_at = Column(DateTime, nullable=True)
    locked = Column(Boolean, nullable=True)

    last_message_at = Column(DateTime, nullable=True, index=True)
    additional_attributes = Column(
        MutableDict.as_mutable(JSON), default=dict, nullable=True
    )

    account = relationship("Account", back_populates="conversations")
    inbox = relationship("Inbox", back_populates="conversations")
    contact_inbox = relationship("ContactInbox", back_populates="conversation")

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="conversation", cascade="all, delete-orphan"
    )
