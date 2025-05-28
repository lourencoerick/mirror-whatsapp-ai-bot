# backend/app/models/usage_event.py
import uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    func as sql_func,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone  # Importado timezone
from typing import Optional  # Para stripe_meter_event_id

from app.models.base import BaseModel

# Se você quiser uma relação explícita com Account, descomente a importação e a relação abaixo
# from app.models.account import Account


class UsageEvent(BaseModel):
    """
    Represents a unit of billable usage to be reported to Stripe.

    Each record typically corresponds to a specific action or resource consumption
    by an account that is subject to metered billing (e.g., number of AI messages generated).
    """

    __tablename__ = "usage_events"

    id: uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    account_id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalized for easier querying by the reporting task,
    # but ensure it's kept in sync if the account's stripe_customer_id can change (rare).
    stripe_customer_id: str = Column(String, nullable=False, index=True)

    meter_event_name: str = Column(
        String,
        nullable=False,
        comment="The 'event_name' of the meter as configured in Stripe (e.g., 'generated_ia_messages')",
    )
    quantity: int = Column(
        Integer,
        nullable=False,
        default=1,
        comment="The amount of usage for this event (e.g., 1 for one message)",
    )

    event_timestamp: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),  # Default para agora em UTC
        comment="Timestamp when the actual usage event occurred",
    )

    reported_to_stripe_at: Optional[datetime] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when this usage event (or an aggregation including it) was successfully reported to Stripe",
    )
    # Optional: Store the ID of the Stripe MeterEvent object after successful reporting
    stripe_meter_event_id: Optional[str] = Column(
        String, nullable=True, unique=True, index=True
    )

    # Se você tiver uma relação definida no modelo Account para usage_events:
    account = relationship("Account", back_populates="usage_events")

    __table_args__ = (
        # Index to quickly find unreported events for a specific account or customer
        Index(
            "ix_usage_events_account_id_meter_name_not_reported",
            "account_id",
            "meter_event_name",
            "reported_to_stripe_at",
            postgresql_where=(reported_to_stripe_at.is_(None)),  # Parcial index
        ),
        Index(
            "ix_usage_events_stripe_customer_id_meter_name_not_reported",
            "stripe_customer_id",
            "meter_event_name",
            "reported_to_stripe_at",
            postgresql_where=(reported_to_stripe_at.is_(None)),  # Parcial index
        ),
        # Index on event_timestamp for potential time-based queries or ordering
        Index("ix_usage_events_event_timestamp", "event_timestamp"),
    )

    def __repr__(self):
        is_reported_str = "Reported" if self.reported_to_stripe_at else "Not Reported"
        return (
            f"<UsageEvent(id={self.id}, account_id={self.account_id}, "
            f"meter='{self.meter_event_name}', quantity={self.quantity}, "
            f"status='{is_reported_str}')>"
        )
