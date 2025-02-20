from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
    BigInteger,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    # Conforme o DDL, o id é INTEGER nesta tabela
    id = Column(Integer, primary_key=True)
    __table_args__ = (
        UniqueConstraint("provider", "uid", name="users_provider_uid_unique"),
        UniqueConstraint(
            "reset_password_token", name="users_reset_password_token_unique"
        ),
        UniqueConstraint("pubsub_token", name="users_pubsub_token_unique"),
        Index("users_email_index", "email"),
    )
    provider = Column(String(255), nullable=False)
    uid = Column(String(255), nullable=False)
    encrypted_password = Column(String(255), nullable=False)
    reset_password_token = Column(String(255), nullable=True)
    reset_password_sent_at = Column(DateTime, nullable=True)
    remember_created_at = Column(DateTime, nullable=True)
    sign_in_count = Column(Integer, nullable=False)
    current_sign_in_at = Column(DateTime, nullable=True)
    last_sign_in_at = Column(DateTime, nullable=True)
    current_sign_in_ip = Column(String(255), nullable=True)
    last_sign_in_ip = Column(String(255), nullable=True)
    confirmation_token = Column(String(255), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    confirmation_sent_at = Column(DateTime, nullable=True)
    unconfirmed_email = Column(String(255), nullable=True)
    name = Column(String(255), nullable=False)
    nickname = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    tokens = Column(JSON, nullable=True)
    pubsub_token = Column(String(255), nullable=True)

    # Relationships
    account_users = relationship(
        "AccountUser", back_populates="user", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="user", cascade="all, delete-orphan"
    )
    inbox_members = relationship(
        "InboxMember", back_populates="user", cascade="all, delete-orphan"
    )
    events = relationship("Event", back_populates="user", cascade="all, delete-orphan")


class AccessToken(BaseModel):
    __tablename__ = "access_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="access_tokens_token_unique"),
        Index("access_tokens_owner_type_owner_id_index", "owner_type", "owner_id"),
    )
    owner_type = Column(String(255), nullable=True)
    owner_id = Column(BigInteger, nullable=True)
    token = Column(String(255), nullable=True)
