from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AgentBotInbox(BaseModel):
    __tablename__ = "agent_bot_inboxes"
    __table_args__ = {"extend_existing": True}
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    inbox_id = Column(UUID(as_uuid=True), ForeignKey("inboxes.id"), nullable=True)
    agent_bot_id = Column(
        UUID(as_uuid=True), ForeignKey("agent_bots.id"), nullable=True
    )
    status = Column(Integer, nullable=True)

    account = relationship("Account", back_populates="agent_bot_inboxes")
    inbox = relationship("Inbox", back_populates="agent_bot_inboxes")
    agent_bot = relationship("AgentBot", back_populates="agent_bot_inboxes")
