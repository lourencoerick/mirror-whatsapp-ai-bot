from typing import TYPE_CHECKING, Optional  # Added TYPE_CHECKING, Optional

import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column,
    String,
    JSON,
    ForeignKey,
    Index,
    DateTime,
    Boolean,
    sql,
)


from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from sqlalchemy.sql import expression


if TYPE_CHECKING:
    from app.models.simulation.persona import Persona


class Contact(BaseModel):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone_number = Column(String(255), nullable=True)
    is_whatsapp_business = Column(Boolean, nullable=True)
    is_whatsapp = Column(Boolean, nullable=True)
    pubsub_token = Column(String(255), nullable=True)
    identifier = Column(String(255), nullable=False)
    profile_picture_url = Column(String(255), nullable=True)
    source_id = Column(String(255), nullable=True)
    additional_attributes = Column(JSON, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=False)

    is_simulation = Column(
        Boolean, nullable=False, default=False, server_default=sql.false(), index=True
    )
    account = relationship(
        "Account",
        back_populates="contacts",
        foreign_keys=[account_id],
    )

    contact_inboxes = relationship(
        "ContactInbox", back_populates="contact", cascade="all, delete-orphan"
    )
    messages = relationship(
        "Message", back_populates="contact", cascade="all, delete-orphan"
    )

    persona = relationship(
        "Persona",
        back_populates="contact",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_contacts_account_id_active",
            "account_id",
            postgresql_where=expression.text("deleted_at IS NULL"),
        ),
        Index(
            "ix_contacts_account_id_identifier_active_unique",
            "account_id",
            "identifier",
            unique=True,
            postgresql_where=expression.text("deleted_at IS NULL"),
        ),
        Index(
            "ix_contacts_email_account_id_active_unique",
            "account_id",
            "email",
            unique=True,
            postgresql_where=expression.text(
                "deleted_at IS NULL AND email IS NOT NULL"
            ),
        ),
        Index(
            "ix_contacts_pubsub_token_active_unique",
            "pubsub_token",
            unique=True,
            postgresql_where=expression.text(
                "deleted_at IS NULL AND pubsub_token IS NOT NULL"
            ),
        ),
        Index(
            "ix_contacts_email_active",
            "email",
            postgresql_where=expression.text(
                "deleted_at IS NULL AND email IS NOT NULL"
            ),
        ),
        Index(
            "ix_contacts_phone_number_active",
            "phone_number",
            postgresql_where=expression.text("deleted_at IS NULL"),
        ),
        Index("contacts_account_id_index", "account_id"),
        Index(
            "ix_contacts_name_gin_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    def __repr__(self):
        is_persona_str = (
            f", persona_id={self.persona.persona_id}" if self.persona else ""
        )
        return (
            f"<Contact(id={self.id}, identifier='{self.identifier}'{is_persona_str})>"
        )
