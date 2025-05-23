# backend/app/api/routers/billing.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.billing import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
)
from app.services.stripe_service import (
    get_or_create_stripe_customer,
    create_stripe_checkout_session,
)
from app.config import get_settings  # Para a chave publicável

settings = get_settings()

# Este router deve ser acessível por usuários autenticados, mesmo sem assinatura ativa.
# Portanto, NÃO o coloque sob a dependência global `require_active_subscription`.
router = APIRouter(
    prefix="/billing",  # Será /api/v1/billing se incluído no api_v1_router
    tags=["Billing & Subscriptions"],
    dependencies=[
        Depends(get_auth_context)
    ],  # Requer autenticação Clerk para todas as rotas aqui
)


@router.post(
    "/create-checkout-session",
    response_model=CreateCheckoutSessionResponse,
    summary="Create Stripe Checkout Session",
    description="Creates a Stripe Checkout session for a user to subscribe to a selected plan.",
)
async def create_checkout_session_endpoint(
    request_data: CreateCheckoutSessionRequest,
    auth_context: AuthContext = Depends(
        get_auth_context
    ),  # Já injetado pela dependência do router
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint to initiate a subscription checkout process.
    - Requires authentication.
    - Retrieves or creates a Stripe Customer for the user's account.
    - Creates a Stripe Checkout Session for the given price_id.
    - Returns the session ID to the frontend for redirection.
    """
    account = auth_context.account
    user = auth_context.user  # Para e-mail e nome, se necessário

    if not account:
        # Isso não deveria acontecer se get_auth_context garante uma conta
        logger.error(
            f"User {user.id if user else 'Unknown'} authenticated but no account found."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Associated account not found.",
        )

    try:
        # 1. Get or Create Stripe Customer
        stripe_customer_id = await get_or_create_stripe_customer(
            db=db,
            account=account,
            clerk_user_id=(
                user.id if user else None
            ),  # Supondo que user.id é o clerk_user_id
            user_email=user.email if user else None,
            user_name=user.name if user else None,
        )

        # 2. Create Stripe Checkout Session
        # Você pode querer passar dados de trial aqui se o price_id não os incluir por padrão
        # Ex: subscription_data={"trial_period_days": 7}
        checkout_session = await create_stripe_checkout_session(
            stripe_customer_id=stripe_customer_id,
            price_id=request_data.price_id,
            app_account_id=account.id,
            # checkout_metadata={"example_key": "example_value"}, # Opcional
            # subscription_data={"trial_period_days": 7} # Opcional para trials
        )

        return CreateCheckoutSessionResponse(
            checkout_session_id=checkout_session.id,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY,  # Enviar a chave publicável
        )

    except stripe.error.StripeError as e:  # type: ignore
        logger.error(
            f"Stripe API error during checkout session creation for Account {account.id}: {str(e)}"
        )
        # Tentar dar uma mensagem de erro mais amigável baseada no tipo de erro do Stripe
        error_message = "Failed to initiate payment session due to a Stripe error."
        if hasattr(e, "user_message") and e.user_message:  # type: ignore
            error_message = e.user_message  # type: ignore
        elif e.http_status == 400:  # type: ignore
            error_message = f"Invalid request to Stripe: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=error_message
        )
    except Exception as e:
        logger.exception(
            f"Unexpected error during checkout session creation for Account {account.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while initiating the payment session.",
        )


# Futuramente:
# @router.post("/create-customer-portal-session", ...)
# async def create_customer_portal_endpoint(...):
#     ...
