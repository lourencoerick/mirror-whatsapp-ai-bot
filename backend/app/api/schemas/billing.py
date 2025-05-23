# backend/app/api/schemas/billing.py

from pydantic import BaseModel, Field
from uuid import UUID


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


# Outros schemas de billing podem ser adicionados aqui no futuro
# class CustomerPortalSessionResponse(BaseModel):
#     portal_url: str
