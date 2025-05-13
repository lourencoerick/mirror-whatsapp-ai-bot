# app/models/whatsapp_cloud_config.py
import uuid
from sqlalchemy import Column, String, ForeignKey, Text, LargeBinary
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class WhatsAppCloudConfig(BaseModel):
    """
    Database model representing the configuration for a WhatsApp Cloud API channel.
    Stores necessary credentials and identifiers to connect to the WhatsApp Cloud API.
    """

    __tablename__ = "whatsapp_cloud_configs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # WhatsApp specific identifiers
    phone_number_id: str = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="WhatsApp Cloud API Phone Number ID.",
    )
    waba_id: str = Column(
        String(255), nullable=False, index=True, comment="WhatsApp Business Account ID."
    )

    # Credentials - consider encryption for access_token if not handled elsewhere
    encrypted_access_token: bytes = Column(
        LargeBinary,
        nullable=False,
        comment="Encrypted System User Access Token (long-lived preferred) for WhatsApp Cloud API.",
    )

    webhook_verify_token: str = Column(
        String(255),
        nullable=False,
        comment="The verify token configured in the Meta App for webhook verification",
    )

    app_id: str = Column(
        String(255),
        nullable=True,
        comment="Meta App ID associated with the WhatsApp integration, if applicable.",
    )

    # account_id to associate this config with an account, similar to EvolutionInstance
    # This ensures that configurations are scoped to accounts.
    account_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account = relationship(
        "Account",
        # If Account model has a `whatsapp_cloud_configs` backref:
        # back_populates="whatsapp_cloud_configs",
        foreign_keys=[account_id],
    )

    inbox = relationship(
        "Inbox",
        back_populates="whatsapp_cloud_config",
        uselist=False,
    )

    def __repr__(self):
        return f"<WhatsAppCloudConfig(id={self.id}, phone_number_id='{self.phone_number_id}')>"
