# backend/app/api/schemas/billing.py

from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID
from typing import Optional
from datetime import datetime
from app.models.subscription import SubscriptionStatusEnum


class CreateCheckoutSessionRequest(BaseModel):
    price_id: str = Field(
        ...,
        description="The ID of the Stripe Price object (e.g., price_xxxxxxxxxxxxxx) for the selected plan.",
    )
    # Você poderia adicionar outros campos aqui se necessário, como cupons, metadados específicos, etc.

    model_config = {
        "json_schema_extra": {
            "examples": [{"price_id": "price_1PGxxxxxxxxxxxxxxxxxxxxx"}]
        }
    }


class CreateCheckoutSessionResponse(BaseModel):
    checkout_session_id: str = Field(
        ..., description="The ID of the created Stripe Checkout Session."
    )
    publishable_key: str = Field(
        ..., description="The Stripe publishable key to be used by the frontend."
    )  # Útil para o frontend
    checkout_url: HttpUrl

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "checkout_session_id": "cs_test_a1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    "publishable_key": "pk_test_xxxxxxxxxxxxxxxxxxxxxxxx",
                }
            ]
        }
    }


class SubscriptionRead(BaseModel):
    """Detailed information about a user's subscription."""

    id: UUID = Field(
        ..., description="Internal unique identifier for the subscription record."
    )
    account_id: UUID = Field(
        ..., description="Identifier of the account this subscription belongs to."
    )

    stripe_subscription_id: str = Field(
        ..., description="Stripe Subscription ID (sub_xxx)."
    )
    stripe_customer_id: str = Field(..., description="Stripe Customer ID (cus_xxx).")
    stripe_product_id: Optional[str] = Field(
        default=None,
        description="Stripe Product ID (prod_xxx) for the subscribed plan.",
    )
    stripe_price_id: str = Field(
        ..., description="Stripe Price ID (price_xxx) for the specific pricing plan."
    )

    status: SubscriptionStatusEnum = Field(
        ...,
        description="Current status of the subscription (e.g., active, trialing, past_due).",
    )

    current_period_start: Optional[datetime] = Field(
        default=None, description="Start of the current billing period (UTC)."
    )
    current_period_end: Optional[datetime] = Field(
        default=None, description="End of the current billing period (UTC)."
    )

    trial_start_at: Optional[datetime] = Field(
        default=None, description="Start of the trial period, if applicable (UTC)."
    )
    trial_ends_at: Optional[datetime] = Field(
        default=None, description="End of the trial period, if applicable (UTC)."
    )

    cancel_at_period_end: bool = Field(
        ...,
        description="True if the subscription is set to cancel at the end of the current period.",
    )
    canceled_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the subscription was actually canceled, if applicable (UTC).",
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the subscription ended definitively, if applicable (UTC).",
    )

    # Campos do seu modelo original que podem ser úteis (opcional)
    # pricing_version: Optional[str] = Field(default=None, description="Internal version of the pricing plan.")
    # billing_plan_name: Optional[str] = Field(default=None, description="User-friendly name of the billing plan.") # Poderia vir do nosso DB ou do Stripe Price nickname

    # Timestamps do nosso BaseModel
    created_at: datetime = Field(
        ...,
        description="Timestamp of when the subscription record was created in our system (UTC).",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp of the last update to the subscription record in our system (UTC).",
    )

    model_config = {
        "from_attributes": True,  # Para permitir criação a partir de objetos ORM (SQLAlchemy)
        "json_schema_extra": {
            "examples": [
                {
                    "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                    "account_id": "f0e9d8c7-b6a5-4321-fedc-ba9876543210",
                    "stripe_subscription_id": "sub_12345ABCDE",
                    "stripe_customer_id": "cus_ABCDE12345",
                    "stripe_product_id": "prod_XYZ789",
                    "stripe_price_id": "price_789XYZ",
                    "status": "active",
                    "current_period_start": "2023-10-01T00:00:00Z",
                    "current_period_end": "2023-11-01T00:00:00Z",
                    "trial_start_at": None,
                    "trial_ends_at": None,
                    "cancel_at_period_end": False,
                    "canceled_at": None,
                    "ended_at": None,
                    "created_at": "2023-10-01T00:00:00Z",
                    "updated_at": "2023-10-01T00:00:00Z",
                }
            ]
        },
    }


class CustomerPortalSessionResponse(BaseModel):
    """Response schema for creating a Stripe Customer Portal session."""

    portal_url: HttpUrl = Field(
        ...,
        description="The URL to redirect the user to for accessing the Stripe Customer Portal.",
        examples=["https://billing.stripe.com/session/b_test_..."],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "portal_url": "https://billing.stripe.com/session/b_test_session_for_customer_portal"
                }
            ]
        }
    }
