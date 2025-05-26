# backend/app/services/stripe_service.py

import stripe
from uuid import UUID
from typing import Optional, Dict, Any, List
from loguru import logger

from app.models.account import Account
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings  # Para URLs de sucesso/cancelamento

settings = get_settings()
METERED_PRICE_IDS: List[str] = [
    "price_1RSTZWQH91QtB7wzTfoDetj6",  # O Price ID do seu log de erro
    "price_1RSV0BQH91QtB7wzKDG4shih",
    "price_1RSV41QH91QtB7wz0puZUrVr",
    "price_1RSVDJQH91QtB7wz1Z6lXrun",
    # Adicione outros Price IDs medidos aqui
    # "price_ANOTHER_METERED_PRICE_ID",
]


async def get_or_create_stripe_customer(
    db: AsyncSession,
    account: Account,
    clerk_user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
) -> str:
    """
    Retrieves an existing Stripe Customer ID for the account or creates a new one.
    Updates the account record with the Stripe Customer ID if a new one is created.
    """
    if account.stripe_customer_id:
        logger.info(
            f"Found existing Stripe Customer ID {account.stripe_customer_id} for Account ID {account.id}"
        )
        # Opcional: verificar se o cliente ainda existe no Stripe
        try:
            stripe.Customer.retrieve(account.stripe_customer_id)
            return account.stripe_customer_id
        except stripe.error.InvalidRequestError as e:
            if e.code == "resource_missing":  # type: ignore
                logger.warning(
                    f"Stripe Customer ID {account.stripe_customer_id} for Account {account.id} not found in Stripe. Will create a new one."
                )
                account.stripe_customer_id = None  # Limpar para forçar criação
            else:
                logger.error(
                    f"Stripe API error retrieving customer {account.stripe_customer_id}: {e}"
                )
                raise

    # Se account.stripe_customer_id era None ou foi resetado acima
    logger.info(
        f"No valid Stripe Customer ID found for Account ID {account.id}. Creating a new one."
    )

    customer_params: Dict[str, Any] = {
        "metadata": {
            "app_account_id": str(account.id),
        }
    }
    if user_email:
        customer_params["email"] = user_email
    if user_name:
        customer_params["name"] = user_name
    if clerk_user_id:
        customer_params["metadata"]["clerk_user_id"] = str(clerk_user_id)

    try:
        customer = stripe.Customer.create(**customer_params)
        stripe_customer_id = customer.id
        logger.info(
            f"Created Stripe Customer {stripe_customer_id} for Account ID {account.id}"
        )

        account.stripe_customer_id = stripe_customer_id
        db.add(account)  # Marcar a conta como modificada
        await db.commit()
        await db.refresh(account)
        logger.info(
            f"Saved Stripe Customer ID {stripe_customer_id} to Account {account.id}"
        )

        return stripe_customer_id
    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe API error while creating customer for Account {account.id}: {e}"
        )
        await db.rollback()  # Rollback se o commit da conta falhar após criação no Stripe
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error creating/saving Stripe customer for Account {account.id}: {e}"
        )
        await db.rollback()
        raise


async def create_stripe_checkout_session(
    stripe_customer_id: str,
    price_id: str,
    app_account_id: UUID,  # Para client_reference_id
    # Opcional: permitir passar metadados específicos para a sessão de checkout
    checkout_metadata: Optional[Dict[str, str]] = None,
    # Opcional: permitir passar dados da assinatura, como trial
    subscription_data: Optional[Dict[str, Any]] = None,
) -> stripe.checkout.Session:  # type: ignore
    """
    Creates a Stripe Checkout Session for a subscription.

    Args:
        stripe_customer_id: The Stripe Customer ID (cus_xxx).
        price_id: The Stripe Price ID (price_xxx) for the subscription.
        app_account_id: The application's internal Account ID for client_reference_id.
        checkout_metadata: Optional metadata for the checkout session.
        subscription_data: Optional data for the subscription (e.g., trial_period_days).

    Returns:
        A Stripe Checkout Session object.

    Raises:
        stripe.error.StripeError: If there's an issue communicating with Stripe.
    """
    logger.info(
        f"Creating Stripe Checkout Session for Customer {stripe_customer_id}, Price {price_id}, Account {app_account_id}"
    )

    line_item: Dict[str, Any] = {"price": price_id}
    if price_id not in METERED_PRICE_IDS:
        # Adiciona quantity apenas se o preço NÃO for medido
        line_item["quantity"] = 1
    else:
        logger.info(
            f"Price ID {price_id} is metered. Quantity will not be set in line_items."
        )

    session_params: Dict[str, Any] = {
        "customer": stripe_customer_id,
        "payment_method_types": [],
        # settings.STRIPE_PAYMENT_METHOD_TYPES
        # or ["card"],  # Ex: ['card', 'boleto']
        "line_items": [
            line_item,
            # {"price": "price_1RSVVIQH91QtB7wzP0OsL7vS", "quantity": 1},
        ],
        "mode": "subscription",
        "success_url": settings.STRIPE_CHECKOUT_SUCCESS_URL
        + "?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": settings.STRIPE_CHECKOUT_CANCEL_URL,
        "client_reference_id": str(app_account_id),
        "payment_method_collection": "if_required",
        "phone_number_collection": {"enabled": True},
        "metadata": checkout_metadata or {},  # Garante que metadata seja um dict
    }

    # Adicionar dados da assinatura (ex: trial) se fornecidos
    if subscription_data:
        session_params["subscription_data"] = subscription_data
        # Exemplo: subscription_data={"trial_period_days": 7}

    # Para coletar endereço de faturamento se necessário para impostos ou Boleto
    # session_params["billing_address_collection"] = "required"
    # session_params["customer_update"] = {"address": "auto"} # Para salvar o endereço no Customer

    try:
        checkout_session = stripe.checkout.Session.create(**session_params)
        logger.info(
            f"Stripe Checkout Session {checkout_session.id} created for Account {app_account_id}"
        )
        return checkout_session
    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe API error creating Checkout Session for Account {app_account_id}, Customer {stripe_customer_id}: {e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error creating Checkout Session for Account {app_account_id}: {e}"
        )
        raise


async def create_stripe_customer_portal_session(
    stripe_customer_id: str, app_account_id: UUID  # For logging and context
) -> stripe.billing_portal.Session:
    """
    Creates a Stripe Customer Portal Session.

    This session allows a customer to manage their subscriptions, payment methods,
    and view their invoice history directly on a Stripe-hosted page.

    Args:
        stripe_customer_id: The Stripe Customer ID (cus_xxx) for whom the portal session is created.
        app_account_id: The application's internal Account ID, primarily for logging.

    Returns:
        A Stripe Billing Portal Session object, containing the URL to redirect the customer.

    Raises:
        stripe.error.StripeError: If there's an issue communicating with Stripe.
        ValueError: If stripe_customer_id is missing.
    """
    if not stripe_customer_id:
        logger.error(
            f"Cannot create customer portal session for Account {app_account_id}: Missing Stripe Customer ID."
        )
        raise ValueError("Stripe Customer ID is required to create a portal session.")

    logger.info(
        f"Creating Stripe Customer Portal Session for Stripe Customer ID: {stripe_customer_id} (Account: {app_account_id})"
    )

    # The return_url is where Stripe will redirect the user after they are done with the portal.
    # This should be a page in your application, e.g., their account/subscription management page.
    return_url = f"{settings.FRONTEND_URL.strip('/')}/dashboard/account/subscription"  # Example return URL

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )
        logger.info(
            f"Stripe Customer Portal Session created: {portal_session.id} for Customer {stripe_customer_id}. URL: {portal_session.url}"
        )
        return portal_session
    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe API error creating Customer Portal Session for Customer {stripe_customer_id} (Account {app_account_id}): {e}"
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error creating Customer Portal Session for Customer {stripe_customer_id} (Account {app_account_id}): {e}"
        )
        raise
