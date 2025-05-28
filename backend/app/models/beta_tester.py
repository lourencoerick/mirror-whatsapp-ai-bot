# backend/app/models/beta_tester.py

import uuid
import enum
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Enum as SQLEnum,
    func as sql_func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from datetime import datetime, timezone
from typing import (
    Optional,
)  # Mantenha se algum campo opcional realmente pode ser None no DB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel  # Ajuste o caminho se necessário


class BetaStatusEnum(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DENIED = "denied"
    INVITED = "invited"


class BetaTester(BaseModel):
    __tablename__ = "beta_testers"

    id: uuid.UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email: str = Column(String, nullable=False, index=True, unique=True)

    # Campos do formulário
    contact_name: Optional[str] = Column(
        String, nullable=True, comment="Full name of the contact person"
    )
    company_name: Optional[str] = Column(String, nullable=True, index=True)
    company_website: Optional[str] = Column(String, nullable=True)
    business_description: Optional[str] = Column(
        Text, nullable=True, comment="Brief description of their business"
    )
    beta_goal: Optional[str] = Column(
        Text, nullable=True, comment="Main objective for joining the beta"
    )

    has_sales_team: Optional[bool] = Column(Boolean, nullable=True)
    sales_team_size: Optional[str] = Column(
        String, nullable=True, comment="e.g., '1-2', '3-5', '6-10', '11-20', '20+'"
    )
    avg_leads_per_period: Optional[str] = Column(
        String, nullable=True, comment="e.g., 'Less than 10/day', '10-50/day'"
    )
    current_whatsapp_usage: Optional[str] = Column(
        String, nullable=True, comment="e.g., 'Manually', 'Other tool', 'Not actively'"
    )
    willing_to_give_feedback: Optional[bool] = Column(Boolean, nullable=True)

    # Status e rastreamento
    status: BetaStatusEnum = Column(
        SQLEnum(
            BetaStatusEnum,
            name="beta_status_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),  # Use _v2 se necessário
        nullable=False,
        default=BetaStatusEnum.PENDING_APPROVAL.value,
        index=True,
    )
    requested_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_func.now(),
    )
    notes_by_admin: Optional[str] = Column(
        Text, nullable=True, comment="Internal notes by admin"
    )

    # Aprovação
    approved_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    approved_by_admin_id: Optional[str] = Column(
        String, nullable=True, comment="Clerk User ID of admin"
    )

    # Chaves Estrangeiras e Relacionamentos
    # Assumindo que uma conta/usuário só pode ter uma solicitação beta.
    account_id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id: uuid.UUID = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Relações (back_populates precisa ser definido nos modelos User e Account)
    user = relationship("User", back_populates="beta_application", uselist=False)
    account = relationship("Account", back_populates="beta_application", uselist=False)

    def __repr__(self):
        return f"<BetaTester(id={self.id}, email='{self.email}', status='{self.status.value}')>"
