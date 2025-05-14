import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.mutable import MutableDict

from sqlalchemy import (
    Column,
    String,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    CheckConstraint,
    JSON,
    Enum as SAEnum,
    sql,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from app.models.conversation import ConversationStatusEnum

from app.models.channels.channel_types import ChannelTypeEnum


class Inbox(BaseModel):
    __tablename__ = "inboxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    channel_id = Column(
        String(255),
        nullable=False,
        comment="Provider-specific ID for the channel (e.g., phone number ID, instance name).",
    )
    name = Column(String(255), nullable=False)
    channel_type = Column(
        SAEnum(
            ChannelTypeEnum,
            name="channel_type_enum",
            native_enum=True,
            values_callable=lambda enum_class: [item.value for item in enum_class],
            create_type=True,
        ),
        nullable=False,
    )

    initial_conversation_status = Column(
        SAEnum(
            ConversationStatusEnum, name="conversation_status_enum", create_type=True
        ),
        default=ConversationStatusEnum.PENDING,
        nullable=True,
        comment="Initial status of the conversation when created",
    )
    is_simulation = Column(
        Boolean, nullable=False, default=False, server_default=sql.false(), index=True
    )
    enable_auto_assignment = Column(Boolean, nullable=True)
    channel_details = Column(MutableDict.as_mutable(JSON), nullable=True, default=dict)

    evolution_instance_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evolution_instances.id", name="fk_inbox_evolution_instance_id"),
        nullable=True,
        unique=True,  # An evolution instance should only be tied to one inbox
    )
    whatsapp_cloud_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "whatsapp_cloud_configs.id", name="fk_inbox_whatsapp_cloud_config_id"
        ),
        nullable=True,
        unique=True,  # A WhatsApp Cloud config should only be tied to one inbox
    )

    # --- Relationships to specific channel configurations ---
    evolution_instance = relationship(
        "EvolutionInstance",
        back_populates="inbox",  # We will define this in EvolutionInstance model
        foreign_keys=[evolution_instance_id],
        uselist=False,  # One-to-one relationship from Inbox's perspective
    )
    whatsapp_cloud_config = relationship(
        "WhatsAppCloudConfig",
        back_populates="inbox",  # We'll add 'inbox' to WhatsAppCloudConfig
        foreign_keys=[whatsapp_cloud_config_id],
        uselist=False,  # One-to-one relationship
    )

    account = relationship(
        "Account",
        back_populates="inboxes",
        foreign_keys=[account_id],
    )
    messages = relationship(
        "Message", back_populates="inbox", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "Conversation", back_populates="inbox", cascade="all, delete-orphan"
    )
    contact_inboxes = relationship(
        "ContactInbox", back_populates="inbox", cascade="all, delete-orphan"
    )
    inbox_members = relationship(
        "InboxMember", back_populates="inbox", cascade="all, delete-orphan"
    )
    bot_agent_inboxes = relationship(
        "BotAgentInbox", back_populates="inbox", cascade="all, delete-orphan"
    )
    webhooks = relationship(
        "Webhook", back_populates="inbox", cascade="all, delete-orphan"
    )
    events = relationship("Event", back_populates="inbox", cascade="all, delete-orphan")

    __table_args__ = (
        Index("inboxes_account_id_index", "account_id"),
        UniqueConstraint(
            "account_id",
            "channel_id",
            "channel_type",
            name="account_inbox_account_id_channel_id_channe_type_unique",
        ),
        CheckConstraint(
            (
                (channel_type == ChannelTypeEnum.WHATSAPP_EVOLUTION)
                & (evolution_instance_id.isnot(None))
                & (whatsapp_cloud_config_id.is_(None))
            )
            | (
                (channel_type == ChannelTypeEnum.WHATSAPP_CLOUD)
                & (whatsapp_cloud_config_id.isnot(None))
                & (evolution_instance_id.is_(None))
            ),
            name="ck_inbox_channel_config_populated",
        ),
        Index("ix_inbox_evolution_instance_id", "evolution_instance_id", unique=True),
        Index(
            "ix_inbox_whatsapp_cloud_config_id", "whatsapp_cloud_config_id", unique=True
        ),
    )

    def __repr__(self):
        return f"<Inbox(id={self.id}, name='{self.name}', channel_type='{self.channel_type.value}')>"
