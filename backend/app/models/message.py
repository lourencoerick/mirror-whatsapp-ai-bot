from sqlalchemy import (
    Column,
    Integer,
    Text,
    String,
    JSON,
    Boolean,
    ForeignKey,
    Index,
    DateTime,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (
        Index("messages_account_id_index", "account_id"),
        Index("messages_inbox_id_index", "inbox_id"),
        Index("messages_conversation_id_index", "conversation_id"),
        Index("messages_user_id_index", "user_id"),
        Index("messages_source_id_index", "source_id"),
        Index("messages_contact_id_index", "contact_id"),
        Index("messages_sent_at_index", "sent_at"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    content = Column(Text, nullable=True)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    message_type = Column(String(50), nullable=False)
    direction = Column(String(50), nullable=False)  # e.g., "in", "out"
    private = Column(Boolean, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(50), nullable=True)  # e.g., "received", "processed"
    source_id = Column(String(255), nullable=True)
    content_type = Column(String(50), nullable=True)  # e.g., "text", "image"
    content_attributes = Column(JSON, nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    sent_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="messages")
    inbox = relationship("Inbox", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages")
    contact = relationship("Contact", back_populates="messages")
