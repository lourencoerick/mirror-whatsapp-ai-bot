from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class BotAgentInbox(BaseModel):
    __tablename__ = "bot_agent_inboxes"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "inbox_id", name="uq_bot_agent_inboxes_account_inbox"
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
    bot_agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("bot_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account = relationship("Account", back_populates="bot_agent_inboxes")
    inbox = relationship("Inbox", back_populates="bot_agent_inboxes")
    bot_agent = relationship("BotAgent", back_populates="bot_agent_inboxes")

    def __repr__(self):
        return f"<BotAgentInbox(account={self.account_id}, inbox={self.inbox_id}, agent={self.bot_agent_id})>"
