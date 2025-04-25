import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AgentBot(BaseModel):
    __tablename__ = "agent_bots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False, default="Assistente Principal")

    first_message = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    use_rag = Column(Boolean, nullable=False, default=False)

    account = relationship("Account", back_populates="agent_bot")

    agent_bot_inboxes = relationship(
        "AgentBotInbox", back_populates="agent_bot", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AgentBot(id={self.id}, name='{self.name}', account_id={self.account_id})>"
