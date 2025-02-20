from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Text,
    String,
    JSON,
    SmallInteger,
    ForeignKey,
    Index,
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
    )
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    content = Column(Text, nullable=True)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    message_type = Column(Integer, nullable=False)
    private = Column(SmallInteger, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Integer, nullable=True)
    source_id = Column(String(255), nullable=True)
    content_type = Column(Integer, nullable=True)
    content_attributes = Column(JSON, nullable=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)

    account = relationship("Account", back_populates="messages")
    inbox = relationship("Inbox", back_populates="messages")
    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages")
    contact = relationship("Contact", back_populates="messages")
