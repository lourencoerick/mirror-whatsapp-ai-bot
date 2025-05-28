# backend/app/api/routers/billing.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
import stripe
from typing import Optional

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.billing import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    SubscriptionRead,
    CustomerPortalSessionResponse,
)

from app.models.subscription import Subscription, SubscriptionStatusEnum
from app.models.account import Account

from app.services.billing.stripe_service import (
    get_or_create_stripe_customer,
    create_stripe_checkout_session,
    create_stripe_customer_portal_session,
)
from app.config import get_settings  # Para a chave publicável

settings = get_settings()


router = APIRouter(
    prefix="/billing",
    tags=["Billing & Subscriptions"],
    dependencies=[Depends(get_auth_context)],
)


@router.post(
    "/create-checkout-session",
    response_model=CreateCheckoutSessionResponse,
    summary="Create Stripe Checkout Session",
    description="Creates a Stripe Checkout session for a user to subscribe to a selected plan.",
)
async def create_checkout_session_endpoint(
    request_data: CreateCheckoutSessionRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CreateCheckoutSessionResponse:
    """
    Initiates a subscription checkout process via Stripe.

    This endpoint requires user authentication. It will:
    1. Retrieve or create a Stripe Customer ID for the user's account.
    2. Create a Stripe Checkout Session for the specified price_id.
    3. Return the Checkout Session ID and Stripe publishable key to the frontend,
       which then redirects the user to Stripe's checkout page.

    Args:
        request_data: Request body containing the `price_id` of the plan to subscribe to.
        auth_context: The authentication context of the current user, providing user and account details.
        db: The SQLAlchemy async session.

    Returns:
        A response containing the Stripe Checkout Session ID and the publishable key.

    Raises:
        HTTPException:
            - 500 if the account is not found (should not happen with `get_auth_context`).
            - 502 if there's an error communicating with Stripe.
            - 500 for other unexpected errors.
    """
    account: Account = auth_context.account
    user = auth_context.user

    if not account:  # Should be guaranteed by get_auth_context
        logger.error(
            f"User {user.id if user else 'Unknown'} authenticated but no account found in create_checkout_session."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Associated account not found.",
        )

    logger.info(
        f"Creating checkout session for Account ID: {account.id}, User ID: {user.id if user else 'N/A'}, Price ID: {request_data.price_id}"
    )

    try:
        stripe_customer_id = await get_or_create_stripe_customer(
            db=db,
            account=account,
            clerk_user_id=(
                user.uid if user else None
            ),  # Assuming user.uid is the Clerk User ID
            user_email=user.email if user else None,
            user_name=user.name if user else None,
        )

        # Example: Pass trial data if the plan itself doesn't define it in Stripe
        # subscription_data = {"trial_period_days": 7} if some_condition else None
        checkout_session = await create_stripe_checkout_session(
            db=db,
            auth_context_user_email=user.email,
            stripe_customer_id=stripe_customer_id,
            price_id=request_data.price_id,
            app_account_id=account.id,  # Used for client_reference_id
            # checkout_metadata={"app_user_id": str(user.id)}, # Optional: more metadata
            # subscription_data=subscription_data
        )

        return CreateCheckoutSessionResponse(
            checkout_session_id=checkout_session.id,
            checkout_url=checkout_session.url,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY,
        )

    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe API error during checkout session creation for Account {account.id}: {str(e)}"
        )
        error_message = "Failed to initiate payment session due to a Stripe error."
        # Try to provide a more user-friendly message if available
        if hasattr(e, "user_message") and e.user_message:  # type: ignore
            error_message = e.user_message  # type: ignore
        elif e.http_status == 400:  # type: ignore
            error_message = (
                f"Invalid request to Stripe: {str(e)}"  # More detail for bad requests
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=error_message
        )
    except Exception as e:
        logger.exception(  # Use .exception to log stack trace for unexpected errors
            f"Unexpected error during checkout session creation for Account {account.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while initiating the payment session.",
        )


@router.get(
    "/my-subscription",
    response_model=Optional[SubscriptionRead],
    summary="Get Current User's Active Subscription",
    description="Retrieves details of the active or trialing subscription for the authenticated user's account. Returns null if no such subscription is found.",
)
async def get_my_subscription_details(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Optional[
    Subscription
]:  # FastAPI will convert Subscription ORM to SubscriptionRead
    """
    Fetches the current active or trialing subscription for the authenticated user's account.

    This endpoint queries the local database for a subscription linked to the user's
    account that has a status of 'active' or 'trialing'. If multiple such
    subscriptions exist (which should be rare for a single primary service),
    it may pick the most recently created or relevant one based on ordering.

    Args:
        auth_context: The authentication context of the current user.
        db: The SQLAlchemy async session.

    Returns:
        The Subscription object if an active or trialing subscription is found,
        otherwise None. FastAPI/Pydantic handles converting this to the
        SubscriptionRead schema or a JSON null.
    """
    account_id: UUID = auth_context.account.id
    logger.info(f"Fetching subscription details for Account ID: {account_id}")

    stmt = (
        select(Subscription)
        .where(Subscription.account_id == account_id)
        .where(
            Subscription.status.in_(
                [
                    SubscriptionStatusEnum.ACTIVE,
                    SubscriptionStatusEnum.TRIALING,
                ]
            )
        )
        # Order by creation date descending to get the latest if multiple (should be rare)
        .order_by(Subscription.created_at.desc())
    )

    result = await db.execute(stmt)
    subscription = result.scalars().first()

    if not subscription:
        logger.info(
            f"No active or trialing subscription found for Account ID: {account_id}"
        )
        return None  # FastAPI will return a 200 OK with a null body

    logger.info(
        f"Found subscription ID {subscription.id} for Account ID: {account_id} with status {subscription.status.value}"
    )
    return subscription


@router.post(
    "/create-customer-portal-session",
    response_model=CustomerPortalSessionResponse,
    summary="Create Stripe Customer Portal Session",
    description="Creates a Stripe Customer Portal session, allowing the user to manage their billing details and subscriptions.",
)
async def create_customer_portal_session_endpoint(
    auth_context: AuthContext = Depends(get_auth_context),
    # db: AsyncSession = Depends(get_db), # Not strictly needed if account has stripe_customer_id
) -> CustomerPortalSessionResponse:
    """
    Generates a URL for the Stripe Customer Portal.

    The user must be authenticated and their account must have a Stripe Customer ID.
    The frontend should redirect the user to the returned `portal_url`.

    Args:
        auth_context: Provides current user and account details.

    Returns:
        Response containing the URL to the Stripe Customer Portal.

    Raises:
        HTTPException:
            - 404 if the account does not have a Stripe Customer ID.
            - 502 if there's an error communicating with Stripe.
            - 500 for other unexpected errors.
    """
    account: Account = auth_context.account

    if not account.stripe_customer_id:
        logger.warning(
            f"Account {account.id} does not have a Stripe Customer ID. Cannot create portal session."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stripe customer information not found for this account. Please subscribe to a plan first or contact support.",
        )

    logger.info(
        f"Creating customer portal session for Account ID: {account.id}, Stripe Customer ID: {account.stripe_customer_id}"
    )

    try:
        portal_session = await create_stripe_customer_portal_session(
            stripe_customer_id=account.stripe_customer_id, app_account_id=account.id
        )

        if not portal_session.url:
            logger.error(
                f"Stripe Customer Portal Session {portal_session.id} created without a URL."
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Customer portal session created without a URL.",
            )

        return CustomerPortalSessionResponse(portal_url=portal_session.url)  # type: ignore

    except ValueError as ve:  # Catch specific ValueError from service
        logger.error(
            f"ValueError creating portal session for Account {account.id}: {ve}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe API error creating customer portal session for Account {account.id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create customer portal session due to a Stripe error.",
        )
    except Exception as e:
        logger.exception(
            f"Unexpected error creating customer portal session for Account {account.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the customer portal session.",
        )
