import enum
from uuid import uuid4
from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum as SAEnum,
    LargeBinary,
)

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship


from app.models.base import BaseModel


class EvolutionInstanceStatus(str, enum.Enum):
    """Possible statuses for the Evolution Instance lifecycle within the platform."""

    PENDING = "PENDING"  # Initial state after record creation, before calling Evo API
    CREATED = "CREATED"  # Successfully called /instance/create on Evo API
    CONNECTED = "CONNECTED"  # Confirmed 'open' state via webhook or API check
    DISCONNECTED = "DISCONNECTED"  # Confirmed 'close' state via webhook or API check
    ERROR = "ERROR"  # Failed during creation or encountered a persistent error
    UNKNOWN = "UNKNOWN"
    CONNECTING = "CONNECTING"
    API_ERROR = "API_ERROR"


class EvolutionInstance(BaseModel):
    """
    Database model representing a logical Evolution API instance
    managed by the platform and running on a shared Evolution server.
    """

    __tablename__ = "evolution_instances"
    __table_args__ = (
        UniqueConstraint("instance_name", name="uq_evolution_instances_instance_name"),
        Index("ix_evolution_instances_instance_name", "instance_name"),
        Index("ix_evolution_instances_status", "status"),
        Index("ix_evolution_instances_account_id", "account_id"),
    )

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    instance_name: str = Column(String(255), nullable=False)
    shared_api_url: str = Column(String(512), nullable=False)
    logical_token_encrypted: bytes = Column(LargeBinary, nullable=False)
    webhook_url: str = Column(String(512), nullable=False)

    status: EvolutionInstanceStatus = Column(
        SAEnum(EvolutionInstanceStatus),
        nullable=False,
        default=EvolutionInstanceStatus.PENDING,
    )

    account_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    account = relationship(
        "Account", back_populates="evolution_instances", foreign_keys=[account_id]
    )

    inbox = relationship(
        "Inbox",
        back_populates="evolution_instance",
        primaryjoin="EvolutionInstance.id == Inbox.evolution_instance_id",
        uselist=False,
    )

    def __repr__(self):
        return f"<EvolutionInstance(id={self.id}, instance_name='{self.instance_name}', status='{self.status.value}')>"
