from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AgentBot(BaseModel):
    __tablename__ = "agent_bots"
    name = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)
    outgoing_url = Column(String(255), nullable=True)

    agent_bot_inboxes = relationship(
        "AgentBotInbox", back_populates="agent_bot", cascade="all, delete-orphan"
    )


class AgentBotInbox(BaseModel):
    __tablename__ = "agent_bot_inboxes"
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    inbox_id = Column(Integer, ForeignKey("inboxes.id"), nullable=True)
    agent_bot_id = Column(Integer, ForeignKey("agent_bots.id"), nullable=True)
    status = Column(Integer, nullable=True)

    account = relationship("Account", back_populates="agent_bot_inboxes")
    inbox = relationship("Inbox", back_populates="agent_bot_inboxes")
    agent_bot = relationship("AgentBot", back_populates="agent_bot_inboxes")
