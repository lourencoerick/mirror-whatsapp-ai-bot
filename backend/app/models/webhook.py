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
