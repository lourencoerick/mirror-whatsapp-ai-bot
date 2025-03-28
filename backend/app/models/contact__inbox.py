import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ContactInbox(BaseModel):
    __tablename__ = "contact_inboxes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    __table_args__ = (
        UniqueConstraint(
            "inbox_id", "source_id", name="contact_inboxes_inbox_id_source_id_unique"
        ),
        Index("contact_inboxes_source_id_index", "source_id"),
    )
    contact_id = Column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False)
    inbox_id = Column(UUID(as_uuid=True), ForeignKey("inboxes.id"), nullable=False)
    source_id = Column(String(255), nullable=False)

    contact = relationship("Contact", back_populates="contact_inboxes")
    inbox = relationship("Inbox", back_populates="contact_inboxes")
    conversation = relationship("Conversation", back_populates="contact_inbox")
