from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
    BigInteger,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Account(BaseModel):
    __tablename__ = "accounts"
    # Para a tabela accounts, o id é INTEGER conforme DDL
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    locale = Column(Integer, nullable=True)

    # Relacionamentos
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
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(Integer, nullable=True)
    inviter_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)

    account = relationship("Account", back_populates="account_users")
    user = relationship("User", back_populates="account_users")
    inviter_user = relationship("User", foreign_keys=[inviter_id])
