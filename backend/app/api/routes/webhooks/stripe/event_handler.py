# backend/app/services/stripe_webhook_handlers.py
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from sqlalchemy import select
from loguru import logger
from datetime import datetime, timezone
from typing import Optional
import stripe  # type: ignore

from app.models.account import Account
from app.models.subscription import Subscription, SubscriptionStatusEnum

# Importações do seu subscription_service.py
from app.services.subscription.subscription_service import (
    provision_account_access,
    update_clerk_user_metadata_after_subscription_change,
)


async def _get_account_id_from_stripe_customer(
    db: AsyncSession, stripe_customer_id: str
) -> Optional[UUID]:
    """Retrieves the internal account ID associated with a Stripe Customer ID.

    Args:
        db: The SQLAlchemy async session.
        stripe_customer_id: The Stripe Customer ID (cus_xxx).

    Returns:
        The UUID of the account if found, otherwise None.
    """
    if not stripe_customer_id:
        logger.debug("Attempted to get account ID with no Stripe Customer ID provided.")
        return None

    stmt = select(Account.id).where(Account.stripe_customer_id == stripe_customer_id)
    result = await db.execute(stmt)
    account_id = result.scalars().first()

    if not account_id:
        logger.warning(f"No account found for Stripe Customer ID: {stripe_customer_id}")
    else:
        logger.debug(
            f"Found Account ID {account_id} for Stripe Customer ID {stripe_customer_id}"
        )
    return account_id


async def _update_or_create_subscription_from_stripe_object(
    db: AsyncSession,
    stripe_sub_object: stripe.Subscription,
    account_id_override: Optional[UUID] = None,
) -> Optional[Subscription]:
    """
    Updates an existing subscription record or creates a new one based on a Stripe Subscription object.

    This function is idempotent. It ensures the local subscription database stays in sync
    with Stripe's subscription data. It populates all relevant fields from the Stripe
    Subscription object into the local Subscription model instance.

    Args:
        db: The SQLAlchemy async session.
        stripe_sub_object: The Stripe Subscription object from a webhook event or API call.
        account_id_override: An optional account ID to associate with the subscription.
            Primarily used during 'checkout.session.completed' where the account ID
            is known from 'client_reference_id'.

    Returns:
        The updated or newly created Subscription ORM object if successful, otherwise None.
        The object is added to the session but not committed by this function.
    """
    logger.info(
        f"Updating/creating local subscription for Stripe Sub ID: {stripe_sub_object.id}, Status: {stripe_sub_object.status}"
    )

    stripe_sub_object = stripe.Subscription.retrieve(stripe_sub_object.id)

    account_id_to_use = account_id_override

    customer_data = stripe_sub_object.customer
    stripe_customer_id_str: Optional[str] = None
    if isinstance(customer_data, str):
        stripe_customer_id_str = customer_data
    elif hasattr(customer_data, "id") and customer_data.id:  # type: ignore
        stripe_customer_id_str = customer_data.id  # type: ignore

    if not stripe_customer_id_str:
        logger.error(
            f"Stripe Subscription {stripe_sub_object.id} is missing a valid customer ID. Customer data: {customer_data}"
        )
        return None

    if not account_id_to_use:
        account_id_to_use = await _get_account_id_from_stripe_customer(
            db, stripe_customer_id_str
        )

    if not account_id_to_use:
        logger.error(
            f"Could not determine internal account_id for Stripe Subscription {stripe_sub_object.id} "
            f"(Stripe Customer: {stripe_customer_id_str}). This subscription might belong to a customer "
            "not yet fully synced or an orphaned Stripe customer."
        )
        return None  # Cannot proceed without an internal account ID

    stmt = select(Subscription).where(
        Subscription.stripe_subscription_id == stripe_sub_object.id
    )
    existing_sub_result = await db.execute(stmt)
    subscription_record = existing_sub_result.scalars().first()

    if not subscription_record:
        subscription_record = Subscription(stripe_subscription_id=stripe_sub_object.id)
        logger.info(
            f"Creating new local Subscription record for Stripe Subscription ID: {stripe_sub_object.id} "
            f"for Account ID: {account_id_to_use}"
        )
    else:
        logger.info(
            f"Updating existing local Subscription record ID {subscription_record.id} "
            f"(Stripe Subscription ID: {stripe_sub_object.id}) for Account ID: {account_id_to_use}"
        )

    subscription_record.account_id = account_id_to_use
    subscription_record.stripe_customer_id = stripe_customer_id_str

    # Extract product and price IDs from the subscription items
    # Stripe usually includes one item for simple subscriptions.
    logger.info(f"Subscription obj: {stripe_sub_object}")
    logger.info(f"Subscription obj Items: {stripe_sub_object.items}")
    if stripe_sub_object.items and stripe_sub_object.items.data:
        primary_item = stripe_sub_object.items.data[0]
        if primary_item and primary_item.price:
            subscription_record.stripe_price_id = primary_item.price.id
            product_data = primary_item.price.product
            if isinstance(product_data, str):  # Product ID string
                subscription_record.stripe_product_id = product_data
            elif hasattr(product_data, "id"):  # Expanded Product object
                subscription_record.stripe_product_id = product_data.id  # type: ignore
            else:
                logger.warning(
                    f"Could not extract Stripe Product ID from item's price.product for sub {stripe_sub_object.id}. Product data: {product_data}"
                )
        else:
            logger.warning(
                f"Primary item or item price missing for Stripe Subscription {stripe_sub_object.id}. Items: {stripe_sub_object.items.data}"
            )
    else:
        logger.warning(
            f"No items found in Stripe Subscription {stripe_sub_object.id} to determine product/price ID."
        )

    try:
        new_status = SubscriptionStatusEnum(stripe_sub_object.status)
        if subscription_record.status != new_status:
            logger.info(
                f"Subscription {stripe_sub_object.id} status changing from {subscription_record.status} to {new_status.value}"
            )
            subscription_record.status = new_status
        else:
            subscription_record.status = (
                new_status  # Ensure it's set even if not changing
            )
    except ValueError:
        logger.warning(
            f"Unknown Stripe subscription status '{stripe_sub_object.status}' for {stripe_sub_object.id}. "
            f"Keeping last known status: {subscription_record.status.value if subscription_record.status else 'None'}."
        )
        if (
            not subscription_record.status
        ):  # Only set to UNPAID if it's a new record and status is unknown
            subscription_record.status = SubscriptionStatusEnum.UNPAID

    subscription_record.current_period_start = (
        datetime.fromtimestamp(stripe_sub_object.current_period_start, tz=timezone.utc)
        if stripe_sub_object.current_period_start
        else None
    )
    subscription_record.current_period_end = (
        datetime.fromtimestamp(stripe_sub_object.current_period_end, tz=timezone.utc)
        if stripe_sub_object.current_period_end
        else None
    )
    subscription_record.trial_start_at = (
        datetime.fromtimestamp(stripe_sub_object.trial_start, tz=timezone.utc)
        if stripe_sub_object.trial_start
        else None
    )
    subscription_record.trial_ends_at = (
        datetime.fromtimestamp(stripe_sub_object.trial_end, tz=timezone.utc)
        if stripe_sub_object.trial_end
        else None
    )
    subscription_record.cancel_at_period_end = bool(
        stripe_sub_object.cancel_at_period_end
    )

    subscription_record.canceled_at = (
        datetime.fromtimestamp(stripe_sub_object.canceled_at, tz=timezone.utc)
        if stripe_sub_object.canceled_at
        else None
    )
    subscription_record.ended_at = (
        datetime.fromtimestamp(stripe_sub_object.ended_at, tz=timezone.utc)
        if stripe_sub_object.ended_at
        else None
    )

    db.add(subscription_record)
    return subscription_record


async def _handle_subscription_lifecycle_update(
    db: AsyncSession,
    stripe_sub_object: stripe.Subscription,
    event_type: str,
    account_id_from_event: Optional[UUID] = None,
):
    """
    Core logic for handling Stripe subscription lifecycle events.

    This function updates the local subscription record, provisions account access
    based on the new subscription state (which updates Account.active_plan_tier),
    and triggers metadata updates for associated Clerk users.

    Args:
        db: The SQLAlchemy async session.
        stripe_sub_object: The Stripe Subscription object from the event.
        event_type: The type of the Stripe event (e.g., "customer.subscription.updated").
        account_id_from_event: The account ID, if directly available from the event
            (e.g., from `client_reference_id` in `checkout.session.completed`).

    Raises:
        HTTPException: If critical processing steps fail (e.g., saving subscription,
                       provisioning access).
    """
    logger.info(
        f"Handling Stripe event: {event_type} for Stripe Subscription ID: {stripe_sub_object.id}"
    )

    subscription_record = await _update_or_create_subscription_from_stripe_object(
        db, stripe_sub_object, account_id_override=account_id_from_event
    )

    if not subscription_record:
        logger.error(
            f"Failed to update or create local subscription for Stripe Sub ID {stripe_sub_object.id} during {event_type}. "
            "This could be due to missing account linkage or an issue with the Stripe object."
        )
        # If we can't even get a subscription_record, it's a significant issue.
        # We might not have an account_id to work with.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,  # Or 500 if it's an internal mapping issue
            detail=f"Failed to process subscription data from Stripe event {event_type}.",
        )

    # At this point, subscription_record should exist and have an account_id
    if not subscription_record.account_id:
        logger.error(
            f"Subscription record {subscription_record.id} (Stripe: {stripe_sub_object.id}) "
            f"is missing an account_id after update/create. This should not happen."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error: Subscription record is missing account association.",
        )

    account_id = subscription_record.account_id

    # Provision access based on the updated subscription_record
    # This will update Account.active_plan_tier
    try:
        await provision_account_access(
            db=db, account_id=account_id, active_subscription=subscription_record
        )
        logger.info(
            f"Account access provisioned/updated for Account {account_id} after event {event_type}."
        )
    except ValueError as ve:  # Raised by provision_account_access if account not found
        logger.error(
            f"ValueError during access provisioning for Account {account_id}: {ve}"
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e_provision:
        logger.exception(
            f"Unexpected error during access provisioning for Account {account_id} after {event_type}: {e_provision}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to provision account access due to an internal error.",
        )

    # Update Clerk user metadata (e.g., plan tier, subscription status)
    # This should be robust and not fail the entire webhook if Clerk API has transient issues.
    try:
        await update_clerk_user_metadata_after_subscription_change(
            db=db, account_id=account_id
        )
        logger.info(
            f"Clerk user metadata update task initiated for Account {account_id} after event {event_type}."
        )
    except Exception as e_clerk_sync:
        # Log as error, but don't raise HTTPException to Stripe for this,
        # as the core subscription update was successful.
        # Consider a retry mechanism for Clerk updates if they are critical and fail.
        logger.error(
            f"Error during Clerk metadata sync for Account {account_id} after {event_type}: {e_clerk_sync}. "
            "The primary subscription update was successful."
        )

    # The database commit will be handled by the main webhook router function
    # after this handler successfully completes.


async def handle_checkout_session_completed(db: AsyncSession, event: stripe.Event):
    """
    Handles the 'checkout.session.completed' Stripe event.

    This event signifies a customer successfully completed Stripe Checkout.
    If for a subscription, it retrieves the new Stripe Subscription object
    and updates the local database, linking it to the account specified
    in `client_reference_id`.

    Args:
        db: The SQLAlchemy async session.
        event: The Stripe Event object (`checkout.session.completed`).

    Raises:
        HTTPException: If required data (client_reference_id, subscription ID)
                       is missing, or if Stripe API calls fail.
    """
    checkout_session = event.data.object
    logger.info(
        f"Processing checkout.session.completed for Stripe Session ID: {checkout_session.id}"
    )

    mode = checkout_session.get("mode")
    if mode != "subscription":
        logger.info(
            f"Checkout session {checkout_session.id} is not for a subscription (mode: {mode}). Skipping."
        )
        return  # Not an error, just not relevant for subscription logic here.

    client_reference_id_str = checkout_session.get("client_reference_id")
    stripe_subscription_id = checkout_session.get("subscription")

    if not client_reference_id_str:
        logger.error(
            f"Checkout session {checkout_session.id} (mode: subscription) completed without client_reference_id. "
            "Cannot link to an internal account."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing client_reference_id in completed checkout session.",
        )

    try:
        account_id = UUID(client_reference_id_str)
    except ValueError:
        logger.error(
            f"Invalid UUID format for client_reference_id: '{client_reference_id_str}' "
            f"in checkout session {checkout_session.id}."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_reference_id format in checkout session.",
        )

    if not stripe_subscription_id:
        logger.error(
            f"Checkout session {checkout_session.id} (mode: subscription) completed "
            "without a subscription ID. Cannot fetch subscription details."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing subscription ID in completed checkout session.",
        )

    try:
        # Retrieve the full Subscription object from Stripe
        stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} "
            f"(from checkout session {checkout_session.id}) from Stripe API: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,  # Error communicating with Stripe
            detail="Failed to retrieve subscription details from Stripe after checkout.",
        )

    # Pass the retrieved account_id directly to the handler
    await _handle_subscription_lifecycle_update(
        db, stripe_sub_object, event.type, account_id_from_event=account_id
    )


async def handle_invoice_payment_succeeded(db: AsyncSession, event: stripe.Event):
    """
    Handles the 'invoice.payment_succeeded' Stripe event.

    This event indicates a successful payment for an invoice. If the invoice
    is for a subscription renewal or initial payment, this handler ensures
    the local subscription record reflects any changes (e.g., becoming active,
    period extension).

    Args:
        db: The SQLAlchemy async session.
        event: The Stripe Event object (`invoice.payment_succeeded`).

    Raises:
        HTTPException: If Stripe API calls to retrieve the subscription fail.
    """
    invoice = event.data.object
    stripe_subscription_id = invoice.get(
        "subscription"
    )  # This is Stripe Subscription ID

    if not stripe_subscription_id:
        logger.info(
            f"Invoice {invoice.id} payment succeeded but is not linked to a subscription "
            "(e.g., one-time payment or setup fee). Skipping subscription update."
        )
        return

    logger.info(
        f"Processing invoice.payment_succeeded for Invoice ID: {invoice.id}, "
        f"linked to Stripe Subscription ID: {stripe_subscription_id}"
    )

    try:
        stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} "
            f"(for invoice.payment_succeeded, Invoice: {invoice.id}) from Stripe API: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve subscription details from Stripe for paid invoice.",
        )

    await _handle_subscription_lifecycle_update(db, stripe_sub_object, event.type)


async def handle_customer_subscription_updated(db: AsyncSession, event: stripe.Event):
    """
    Handles 'customer.subscription.updated' and similar lifecycle Stripe events.

    Events like '.created', '.updated', '.trial_will_end' signify changes to a
    subscription's state (e.g., plan changes, status updates like 'past_due',
    'active', trial period modifications). This handler updates the local
    subscription record to mirror these changes.

    Args:
        db: The SQLAlchemy async session.
        event: The Stripe Event object (e.g., `customer.subscription.updated`),
               where `event.data.object` is the Stripe Subscription.
    """
    stripe_sub_object = event.data.object  # This is the Stripe Subscription object
    logger.info(
        f"Processing {event.type} for Stripe Subscription ID: {stripe_sub_object.id}"
    )
    await _handle_subscription_lifecycle_update(db, stripe_sub_object, event.type)


async def handle_customer_subscription_deleted(db: AsyncSession, event: stripe.Event):
    """
    Handles the 'customer.subscription.deleted' Stripe event.

    This event means a subscription was canceled and its term ended, or it was
    canceled immediately. The handler updates the local subscription record,
    typically marking its status as 'canceled' or 'ended'.

    Args:
        db: The SQLAlchemy async session.
        event: The Stripe Event object (`customer.subscription.deleted`),
               where `event.data.object` is the (now deleted/canceled) Stripe Subscription.
    """
    stripe_sub_object = event.data.object  # Status will likely be 'canceled'
    logger.info(
        f"Processing customer.subscription.deleted for Stripe Subscription ID: {stripe_sub_object.id}"
    )
    await _handle_subscription_lifecycle_update(db, stripe_sub_object, event.type)


async def handle_invoice_payment_failed(db: AsyncSession, event: stripe.Event):
    """
    Handles the 'invoice.payment_failed' Stripe event.

    Occurs when a payment attempt for an invoice (often for subscription renewal) fails.
    The handler updates the local subscription record, potentially changing its status
    to 'past_due' or 'unpaid', reflecting Stripe's dunning process.

    Args:
        db: The SQLAlchemy async session.
        event: The Stripe Event object (`invoice.payment_failed`).

    Raises:
        HTTPException: If Stripe API calls to retrieve the subscription fail.
    """
    invoice = event.data.object
    stripe_subscription_id = invoice.get("subscription")

    if not stripe_subscription_id:
        logger.warning(
            f"Invoice {invoice.id} payment failed but is not linked to a subscription. "
            "Skipping subscription update."
        )
        return

    logger.info(
        f"Processing invoice.payment_failed for Invoice ID: {invoice.id}, "
        f"linked to Stripe Subscription ID: {stripe_subscription_id}"
    )

    try:
        stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} "
            f"(for invoice.payment_failed, Invoice: {invoice.id}) from Stripe API: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve subscription details from Stripe for failed invoice.",
        )

    await _handle_subscription_lifecycle_update(db, stripe_sub_object, event.type)
