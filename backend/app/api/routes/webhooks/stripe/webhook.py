# backend/app/api/routes/webhooks/stripe.py

from fastapi import APIRouter, Request, Header, HTTPException, status, Response, Depends
from loguru import logger
import stripe  # For stripe.error and stripe.Webhook
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

# Updated import path for webhook handlers
from .event_handler import (
    handle_checkout_session_completed,
    handle_invoice_payment_succeeded,
    handle_customer_subscription_updated,
    handle_customer_subscription_deleted,
    handle_invoice_payment_failed,
)
from app.database import get_db
from app.config import get_settings


settings = get_settings()

router = APIRouter(
    prefix="/webhooks",  # Prefix is already defined in main.py when including this router
    tags=["Stripe Webhooks"],  # Tag updated for clarity, main.py uses "Stripe Webhooks"
    # This router should NOT have global auth dependencies from our API
)


@router.post(
    "/stripe",  # Path will be /webhooks/stripe due to prefix in main.py
    include_in_schema=False,  # Keep out of public OpenAPI docs
)
async def stripe_webhook_endpoint(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint to receive and process webhooks from Stripe.

    Verifies the signature of the incoming request to ensure it's from Stripe,
    then processes the event by dispatching it to the appropriate handler.
    A 200 OK response must be sent to Stripe quickly to acknowledge receipt.
    Any actual processing can happen subsequently or be offloaded to a background task
    if it's time-consuming.

    Args:
        request: The FastAPI Request object, used to get the raw request body.
        stripe_signature: The 'Stripe-Signature' header from the request.
        db: The SQLAlchemy async session, injected by FastAPI.

    Returns:
        A FastAPI Response object, typically 200 OK if the event is acknowledged.

    Raises:
        HTTPException: For various errors like missing signature, invalid payload,
                       signature verification failure, or internal processing errors.
    """
    if not stripe_signature:
        logger.warning("Stripe webhook received without Stripe-Signature header.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    payload = await request.body()
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    if not endpoint_secret:
        logger.error(
            "STRIPE_WEBHOOK_SECRET is not configured. Cannot verify webhook signature."
        )
        # This is a server configuration error. Stripe expects a 2xx or 4xx.
        # Returning 500 might cause Stripe to retry, but we can't process it anyway.
        # For security, don't reveal the secret is missing.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing configuration error.",
        )

    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, endpoint_secret
        )
        logger.info(f"Stripe webhook event received: ID={event.id}, Type={event.type}")
    except ValueError as e:
        logger.error(f"Stripe webhook error: Invalid payload. {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError as e:  # type: ignore
        logger.error(f"Stripe webhook error: Invalid signature. {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature"
        )
    except Exception as e:
        logger.error(f"Stripe webhook error: Could not construct event. {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not construct event"
        )

    # Optional: Log the full event for debugging, can be verbose
    # logger.debug(f"Stripe Event Full Payload: {event}")

    # Map event types to handlers
    event_handlers = {
        "checkout.session.completed": handle_checkout_session_completed,
        "invoice.payment_succeeded": handle_invoice_payment_succeeded,
        "customer.subscription.updated": handle_customer_subscription_updated,
        "customer.subscription.created": handle_customer_subscription_updated,  # Often similar logic to updated
        "customer.subscription.trial_will_end": handle_customer_subscription_updated,  # Or a specific handler
        "customer.subscription.deleted": handle_customer_subscription_deleted,
        "invoice.payment_failed": handle_invoice_payment_failed,
    }

    handler = event_handlers.get(event.type)

    if not handler:
        logger.info(f"Received unhandled Stripe event type: {event.type}")
        # Acknowledge receipt even if not handled to prevent Stripe from resending.
        return Response(
            status_code=status.HTTP_200_OK,
            content=f"Webhook for {event.type} received but not handled.",
        )

    try:
        await handler(db=db, event=event)
        await db.commit()  # Commit transaction if handler was successful
        logger.info(
            f"Successfully processed and committed changes for event {event.id} (Type: {event.type})"
        )
        return Response(
            status_code=status.HTTP_200_OK,
            content="Webhook received and processed successfully.",
        )
    except HTTPException as http_exc:  # Re-raise HTTPExceptions from handlers
        await db.rollback()
        logger.warning(
            f"HTTPException during processing event {event.id} (Type: {event.type}): {http_exc.detail}. Stripe might retry."
        )
        raise  # FastAPI will handle sending the response
    except Exception as e:
        await db.rollback()
        logger.exception(  # Use logger.exception for full stack trace
            f"Critical error processing Stripe event {event.type} ({event.id}): {e}"
        )
        # Return a 500 to indicate an issue on our end; Stripe may retry.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook event processing failed internally.",
        ) from e
