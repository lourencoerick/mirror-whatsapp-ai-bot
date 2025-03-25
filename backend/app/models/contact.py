from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Contact(BaseModel):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    __table_args__ = (
        UniqueConstraint(
            "account_id", "identifier", name="contacts_account_id_identifier_unique"
        ),
        UniqueConstraint(
            "email", "account_id", name="contacts_email_account_id_unique"
        ),
        UniqueConstraint("pubsub_token", name="contacts_pubsub_token_unique"),
        Index("contacts_account_id_index", "account_id"),
    )
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(255), nullable=True)
    pubsub_token = Column(String(255), nullable=True)
    identifier = Column(String(255), nullable=True)
    source_id = Column(String(255), nullable=True)
    additional_attributes = Column(JSON, nullable=True)

    account = relationship("Account", back_populates="contacts")
    contact_inboxes = relationship(
        "ContactInbox", back_populates="contact", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="contact", cascade="all, delete-orphan"
    )
