from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
    BigInteger,
    Enum,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.subscription_models import Subscription
from app.models.webhook_event_models import Webhook
from app.models.agent_models import AgentBotInbox
import enum


class UserRole(enum.Enum):
    ADMIN = "admin"
    AGENT = "agent"
    VIEWER = "viewer"
    BOT = "bot"


class Account(BaseModel):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
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


class AccountUser(BaseModel):
    __tablename__ = "account_users"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "user_id", name="account_users_account_id_user_id_unique"
        ),
        Index("account_users_account_id_index", "account_id"),
        Index("account_users_user_id_index", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(Enum(UserRole), nullable=True)
    inviter_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)

    account = relationship(
        "Account", back_populates="account_users", foreign_keys=[account_id]
    )
    user = relationship("User", back_populates="account_users", foreign_keys=[user_id])
    inviter_user = relationship("User", foreign_keys=[inviter_id])
