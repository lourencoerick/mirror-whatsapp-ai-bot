from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AgentBotInbox(BaseModel):
    __tablename__ = "agent_bot_inboxes"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "inbox_id", name="uq_agent_bot_inboxes_account_inbox"
        ),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    account_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    inbox_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("inboxes.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    )
    agent_bot_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_bots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account = relationship("Account", back_populates="agent_bot_inboxes")
    inbox = relationship("Inbox", back_populates="agent_bot_inboxes")
    agent_bot = relationship("AgentBot", back_populates="agent_bot_inboxes")

    def __repr__(self):
        return f"<AgentBotInbox(account={self.account_id}, inbox={self.inbox_id}, agent={self.agent_bot_id})>"
