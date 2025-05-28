from sqlalchemy.dialects.postgresql import UUID
import uuid

from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum
from typing import Optional
import enum

from sqlalchemy.orm import relationship
from app.models.base import BaseModel
from .contact import Contact
from .inbox import Inbox
from .conversation import Conversation
from .subscription import Subscription


class AccountPlanTierEnum(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Account(BaseModel):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    locale = Column(String(5), nullable=True)
    active_plan_tier = Column(
        SQLEnum(
            AccountPlanTierEnum,
            name="account_plan_tier_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
        default=AccountPlanTierEnum.FREE,
        index=True,
        comment="Current active plan tier for the account (e.g., free, basic, pro)",
    )

    simulation_inbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "inboxes.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_account_sim_inbox",
        ),  # use_alter=True needed for potential circular dependency during creation
        nullable=True,
        index=True,  # Index for potential future lookups based on sim inbox
    )
    simulation_contact_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "contacts.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_account_sim_contact",
        ),
        nullable=True,
    )
    simulation_conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "conversations.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_account_sim_convo",
        ),
        nullable=True,
    )

    account_users = relationship(
        "AccountUser", back_populates="account", cascade="all, delete-orphan"
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
    bot_agent_inboxes = relationship(
        "BotAgentInbox", back_populates="account", cascade="all, delete-orphan"
    )

    bot_agent = relationship(
        "BotAgent", back_populates="account", cascade="all, delete-orphan"
    )

    evolution_instances = relationship(
        "EvolutionInstance", back_populates="account", cascade="all, delete-orphan"
    )

    profile = relationship(
        "CompanyProfile",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )

    knowledge_documents = relationship(
        "KnowledgeDocument", back_populates="account", cascade="all, delete-orphan"
    )

    knowledge_chunks = relationship(
        "KnowledgeChunk", back_populates="account", cascade="all, delete-orphan"
    )

    usage_events = relationship(
        "UsageEvent",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    beta_application = relationship(
        "BetaTester",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ------------------ relacionamentos de produção ------------------

    contacts = relationship(
        "Contact",
        back_populates="account",
        foreign_keys=lambda: [Contact.account_id],  # FK clara
        cascade="all, delete-orphan",
    )

    inboxes = relationship(
        "Inbox",
        back_populates="account",
        foreign_keys=lambda: [Inbox.account_id],
        cascade="all, delete-orphan",
    )

    conversations = relationship(
        "Conversation",
        back_populates="account",
        foreign_keys=lambda: [Conversation.account_id],
        cascade="all, delete-orphan",
    )

    # ------------------ relacionamentos de simulação -----------------
    simulation_contact = relationship(
        "Contact",
        primaryjoin="Account.simulation_contact_id == Contact.id",
        foreign_keys=[simulation_contact_id],
        uselist=False,
        overlaps="contacts",  # evita warning de relação sobreposta
    )

    simulation_inbox = relationship(
        "Inbox",
        primaryjoin="Account.simulation_inbox_id == Inbox.id",
        foreign_keys=[simulation_inbox_id],
        uselist=False,
        overlaps="inboxes",
    )

    simulation_conversation = relationship(
        "Conversation",
        primaryjoin="Account.simulation_conversation_id == Conversation.id",
        foreign_keys=[simulation_conversation_id],
        uselist=False,
        overlaps="conversations",
    )
