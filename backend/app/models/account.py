from sqlalchemy.dialects.postgresql import UUID
import uuid

from sqlalchemy import Column, String, ForeignKey


from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Account(BaseModel):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    locale = Column(String(5), nullable=True)

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

    knowledge_documents = relationship("KnowledgeDocument", back_populates="account")

    knowledge_chunks = relationship("KnowledgeChunk", back_populates="account")
