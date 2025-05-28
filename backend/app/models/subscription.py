# backend/app/models/subscription.py (ou onde quer que esteja)

import uuid
import enum  # Para o status da assinatura
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # Usar alias para clareza
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Boolean,
    Index,
)
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import relationship, Mapped  # Usar Mapped para anotações de tipo
from app.models.base import BaseModel


# Enum para o status da assinatura, alinhado com os status do Stripe (ou um subconjunto)
class SubscriptionStatusEnum(str, enum.Enum):
    ACTIVE = "active"  # Assinatura ativa e paga
    PAST_DUE = "past_due"  # Pagamento falhou, mas ainda tentando
    UNPAID = "unpaid"  # Falhou em todas as tentativas de pagamento, pode ser movida para canceled
    CANCELED = "canceled"  # Assinatura cancelada (pode ter sido cancelada pelo usuário ou por falha de pagamento)
    INCOMPLETE = "incomplete"  # Requer ação do usuário para ativar (ex: 3D Secure)
    INCOMPLETE_EXPIRED = "incomplete_expired"  # Incompleta e expirou
    TRIALING = "trialing"  # Em período de teste gratuito
    ENDED = "ended"  # Assinatura completou seu ciclo e não foi renovada (raro para auto-renew)
    # Poderíamos adicionar 'paused' se oferecermos essa funcionalidade


class Subscription(BaseModel):
    __tablename__ = "subscriptions"

    # Chave primária do nosso sistema
    id: Mapped[uuid.UUID] = Column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Ligação com a nossa conta
    account_id: Mapped[uuid.UUID] = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # IDs do Stripe
    stripe_subscription_id: Mapped[str] = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Stripe Subscription ID (sub_xxx)",
    )
    stripe_customer_id: Mapped[str] = Column(
        String(255), nullable=False, index=True, comment="Stripe Customer ID (cus_xxx)"
    )
    stripe_product_id: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        comment="Stripe Product ID (prod_xxx) for the subscribed plan",
    )  # Opcional se você só tem um produto por assinatura
    stripe_price_id: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Stripe Price ID (price_xxx) for the specific pricing plan",
    )

    # Status da Assinatura (sincronizado com o Stripe via webhooks)
    status: Mapped[SubscriptionStatusEnum] = Column(
        SQLEnum(
            SubscriptionStatusEnum,
            name="subscription_status_enum",
            create_type=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
        comment="Current status of the subscription, synced from Stripe",
    )

    # Detalhes do Período de Cobrança Atual
    current_period_start: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Start of the current billing period (from Stripe)",
    )
    current_period_end: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="End of the current billing period (from Stripe)",
    )

    # Detalhes do Trial (se aplicável)
    trial_start_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Start of the trial period (from Stripe)",
    )
    trial_ends_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="End of the trial period (from Stripe)",
    )

    # Informações de Cancelamento
    cancel_at_period_end: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True if the subscription is set to cancel at the end of the current period",
    )
    canceled_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the subscription was actually canceled (from Stripe)",
    )
    ended_at: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the subscription ended definitively (from Stripe)",
    )  # Se não for renovar

    # Metadados (opcional, para armazenar informações extras que vêm do Stripe ou que queremos associar)
    # metadata: Mapped[Optional[dict]] = Column(JSONB, nullable=True)

    # Campos que você tinha (podemos mantê-los ou mapeá-los para os novos)
    # pricing_version: Mapped[Optional[str]] = Column(String(255), nullable=True) # Pode ser útil
    # billing_plan: Mapped[Optional[str]] = Column(String(255), nullable=True) # stripe_price_id ou um nome interno nosso

    # Relacionamento com Account
    account: Mapped["Account"] = relationship(
        "Account", back_populates="subscriptions"
    )  # Usar string para forward reference

    # Adicionar um UniqueConstraint para account_id e stripe_subscription_id se uma conta só pode ter uma instância de uma sub específica
    # Ou, se uma conta pode ter múltiplas assinaturas (ex: para diferentes produtos), então stripe_subscription_id deve ser único globalmente.
    # Se uma conta só pode ter UMA assinatura ATIVA de um determinado tipo de produto, a lógica de negócio controla isso.
    # Por simplicidade, vamos assumir que uma conta pode ter no máximo uma assinatura ativa para um produto/serviço principal.
    # O stripe_subscription_id já é único.
    __table_args__ = (
        Index(
            "ix_subscriptions_account_id_status", "account_id", "status"
        ),  # Para buscar assinaturas ativas de uma conta
    )

    def __repr__(self):
        return f"<Subscription(id={self.id}, account_id={self.account_id}, stripe_subscription_id='{self.stripe_subscription_id}', status='{self.status.value}')>"
