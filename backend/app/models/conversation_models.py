from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    DateTime,
    SmallInteger,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Conversation(BaseModel):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "display_id",
            name="conversations_account_id_display_id_unique",
        ),
        Index("conversations_account_id_index", "account_id"),
        Index("conversations_contact_inbox_id_index", "contact_inbox_id"),
    )
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=False)
    status = Column(Integer, nullable=False)
    assignee_id = Column(Integer, nullable=True)
    contact_id = Column(BigInteger, ForeignKey("contacts.id"), nullable=True)
    display_id = Column(Integer, nullable=False)
    user_last_seen_at = Column(DateTime, nullable=True)
    agent_last_seen_at = Column(DateTime, nullable=True)
    locked = Column(SmallInteger, nullable=True)
    contact_inbox_id = Column(Integer, ForeignKey("contact_inboxes.id"), nullable=True)
    additional_attributes = Column(JSON, nullable=True)

    account = relationship("Account", back_populates="conversations")
    inbox = relationship("Inbox", back_populates="conversations")
    contact = relationship("Contact", back_populates="conversations")
    # Se necessário, relacionamento com ContactInbox:
    contact_inbox = relationship("ContactInbox")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="conversation", cascade="all, delete-orphan"
    )
