from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Webhook(BaseModel):
    __tablename__ = "webhooks"
    __table_args__ = (
        UniqueConstraint("account_id", "url", name="webhooks_account_id_url_unique"),
    )
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=True)
    url = Column(String(255), nullable=True)
    webhook_type = Column(Integer, nullable=True)

    account = relationship("Account", back_populates="webhooks")
    inbox = relationship("Inbox", back_populates="webhooks")


class Event(BaseModel):
    __tablename__ = "events"
    __table_args__ = (
        Index("events_name_index", "name"),
        Index("events_account_id_index", "account_id"),
        Index("events_inbox_id_index", "inbox_id"),
        Index("events_user_id_index", "user_id"),
        Index("events_created_at_index", "created_at"),
    )
    name = Column(String(255), nullable=True)
    value = Column(Float, nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)

    account = relationship("Account", back_populates="events")
    inbox = relationship("Inbox", back_populates="events")
    user = relationship("User", back_populates="events")
    conversation = relationship("Conversation", back_populates="events")
