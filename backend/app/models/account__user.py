from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    UniqueConstraint,
    Index,
    BigInteger,
    Enum,
)
import enum
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class UserRole(enum.Enum):
    ADMIN = "admin"
    AGENT = "agent"
    VIEWER = "viewer"
    BOT = "bot"


class AccountUser(BaseModel):
    __tablename__ = "account_users"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "user_id", name="account_users_account_id_user_id_unique"
        ),
        Index("account_users_account_id_index", "account_id"),
        Index("account_users_user_id_index", "user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    role = Column(Enum(UserRole), nullable=True)
    inviter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    account = relationship(
        "Account", back_populates="account_users", foreign_keys=[account_id]
    )
    user = relationship("User", back_populates="account_users", foreign_keys=[user_id])
    inviter_user = relationship("User", foreign_keys=[inviter_id])
