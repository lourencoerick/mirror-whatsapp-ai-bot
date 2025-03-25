from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AgentBot(BaseModel):
    __tablename__ = "agent_bots"
    __table_args__ = {"extend_existing": True}
    name = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)
    outgoing_url = Column(String(255), nullable=True)

    agent_bot_inboxes = relationship(
        "AgentBotInbox", back_populates="agent_bot", cascade="all, delete-orphan"
    )
