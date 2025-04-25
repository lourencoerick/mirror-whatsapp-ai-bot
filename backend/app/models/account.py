from sqlalchemy.dialects.postgresql import UUID
import uuid

from sqlalchemy import (
    Column,
    Integer,
    String,
)


from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Account(BaseModel):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    locale = Column(String(5), nullable=True)

    account_users = relationship(
        "AccountUser", back_populates="account", cascade="all, delete-orphan"
    )
    contacts = relationship(
        "Contact", back_populates="account", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "Conversation", back_populates="account", cascade="all, delete-orphan"
    )
    inboxes = relationship(
        "Inbox", back_populates="account", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="account", cascade="all, delete-orphan"
    )
    subscriptions = relationship(
        "Subscription", back_populates="account", cascade="all, delete-orphan"
    )
    webhooks = relationship(
        "Webhook", back_populates="account", cascade="all, delete-orphan"
    )
    events = relationship(
        "Event", back_populates="account", cascade="all, delete-orphan"
    )
    agent_bot_inboxes = relationship(
        "AgentBotInbox", back_populates="account", cascade="all, delete-orphan"
    )

    agent_bot = relationship(
        "AgentBot", back_populates="account", cascade="all, delete-orphan"
    )

    evolution_instances = relationship(
        "EvolutionInstance", back_populates="account", cascade="all, delete-orphan"
    )

    profile = relationship(
        "CompanyProfile",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )
