# backend/app/services/stripe_webhook_handlers.py
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from sqlalchemy import select
from loguru import logger
from datetime import datetime, timezone
from typing import Optional, Dict, Any
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
    stripe_sub_data: Dict[str, Any],  # Tratar como dicionário
    account_id_override: Optional[UUID] = None,
) -> Optional[Subscription]:
    """
    Updates an existing subscription record or creates a new one based on Stripe subscription data.

    This function is idempotent and expects the Stripe subscription data as a dictionary.
    It populates all relevant fields from the Stripe data into the local Subscription model.

    Args:
        db: The SQLAlchemy async session.
        stripe_sub_data: A dictionary representing the Stripe Subscription object.
        account_id_override: An optional account ID to associate with the subscription.
            Primarily used during 'checkout.session.completed'.

    Returns:
        The updated or newly created Subscription ORM object if successful, otherwise None.
        The object is added to the session but not committed by this function.
    """
    sub_id = stripe_sub_data.get("id")
    sub_status_str = stripe_sub_data.get("status")
    logger.info(
        f"Updating/creating local subscription for Stripe Sub ID: {sub_id}, Status: {sub_status_str}"
    )
    # logger.debug(f"Full Stripe Subscription data for {sub_id}: {stripe_sub_data}")

    account_id_to_use = account_id_override

    customer_data = stripe_sub_data.get("customer")
    stripe_customer_id_str: Optional[str] = None

    if isinstance(customer_data, str):
        stripe_customer_id_str = customer_data
    elif isinstance(customer_data, dict) and customer_data.get("id"):
        stripe_customer_id_str = customer_data.get("id")
    # Fallback se for um objeto Stripe real (menos provável se a entrada for Dict[str, Any])
    elif hasattr(customer_data, "id") and getattr(customer_data, "id", None):
        stripe_customer_id_str = getattr(customer_data, "id")

    if not stripe_customer_id_str:
        logger.error(
            f"Stripe Subscription {sub_id} is missing a valid customer ID. Customer data: {customer_data}"
        )
        return None

    if not account_id_to_use:
        account_id_to_use = await _get_account_id_from_stripe_customer(
            db, stripe_customer_id_str
        )

    if not account_id_to_use:
        logger.error(
            f"Could not determine internal account_id for Stripe Subscription {sub_id} "
            f"(Stripe Customer: {stripe_customer_id_str}). This subscription might belong to a customer "
            "not yet fully synced or an orphaned Stripe customer."
        )
        return None

    stmt = select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
    existing_sub_result = await db.execute(stmt)
    subscription_record = existing_sub_result.scalars().first()

    if not subscription_record:
        subscription_record = Subscription(stripe_subscription_id=sub_id)
        logger.info(
            f"Creating new local Subscription record for Stripe Subscription ID: {sub_id} "
            f"for Account ID: {account_id_to_use}"
        )
    else:
        logger.info(
            f"Updating existing local Subscription record ID {subscription_record.id} "
            f"(Stripe Subscription ID: {sub_id}) for Account ID: {account_id_to_use}"
        )

    subscription_record.account_id = account_id_to_use
    subscription_record.stripe_customer_id = stripe_customer_id_str
    ts_cps = None
    ts_cpe = None
    ts_ts = None
    ts_te = None
    ts_ca = None
    ts_ea = None

    # Acessar items, price, product como dicionário
    items_data_dict = stripe_sub_data.get("items")
    if isinstance(items_data_dict, dict):
        items_list = items_data_dict.get("data")
        if isinstance(items_list, list) and len(items_list) > 0:
            primary_item_dict = items_list[0]

            ts_cps = primary_item_dict.get("current_period_start")
            ts_cpe = primary_item_dict.get("current_period_end")
            ts_ts = primary_item_dict.get("trial_start")
            ts_te = primary_item_dict.get("trial_end")
            ts_ca = primary_item_dict.get("canceled_at")
            ts_ea = primary_item_dict.get("ended_at")
            target_pricing_object = primary_item_dict.get("price")

            if target_pricing_object:
                subscription_record.stripe_price_id = target_pricing_object.get("id")
                product_id_val = target_pricing_object.get("product")
                if isinstance(product_id_val, str):
                    subscription_record.stripe_product_id = product_id_val
                else:  # Se product for um objeto expandido (raro aqui, mas possível)
                    logger.warning(
                        f"Product ID for sub {sub_id} in pricing object {target_pricing_object.get('id')} is not a string: {type(product_id_val)}. Value: {product_id_val}"
                    )
            else:
                logger.warning(
                    f"Primary item for sub {sub_id} does not have a valid 'price' or 'plan' dictionary. Item: {primary_item_dict}"
                )
        elif isinstance(items_list, list) and len(items_list) == 0:
            logger.warning(f"items.data for sub {sub_id} is an empty list.")
        else:
            logger.warning(
                f"items.data for sub {sub_id} is not a list or is missing. items.data: {items_list}"
            )

    try:
        if sub_status_str:
            new_status_enum = SubscriptionStatusEnum(sub_status_str)
            if subscription_record.status != new_status_enum:
                current_status_val_log = (
                    subscription_record.status.value
                    if subscription_record.status
                    else "None"
                )
                logger.info(
                    f"Subscription {sub_id} status changing from {current_status_val_log} to {new_status_enum.value}"
                )
            subscription_record.status = new_status_enum
        else:
            logger.warning(
                f"Subscription {sub_id} has no status string. Defaulting to UNPAID if new and no prior status."
            )
            if (
                not subscription_record.status
            ):  # Somente se for um novo registro sem status prévio
                subscription_record.status = SubscriptionStatusEnum.UNPAID
    except ValueError:  # Se sub_status_str não for um valor válido no Enum
        current_status_val_log = (
            subscription_record.status.value if subscription_record.status else "None"
        )
        logger.warning(
            f"Unknown Stripe subscription status string '{sub_status_str}' for {sub_id}. "
            f"Keeping last known status: {current_status_val_log}."
        )
        if (
            not subscription_record.status
        ):  # Somente se for um novo registro sem status prévio e o status do Stripe for inválido
            subscription_record.status = SubscriptionStatusEnum.UNPAID

    subscription_record.current_period_start = (
        datetime.fromtimestamp(ts_cps, tz=timezone.utc)
        if isinstance(ts_cps, int)
        else None
    )
    subscription_record.current_period_end = (
        datetime.fromtimestamp(ts_cpe, tz=timezone.utc)
        if isinstance(ts_cpe, int)
        else None
    )
    subscription_record.trial_start_at = (
        datetime.fromtimestamp(ts_ts, tz=timezone.utc)
        if isinstance(ts_ts, int)
        else None
    )
    subscription_record.trial_ends_at = (
        datetime.fromtimestamp(ts_te, tz=timezone.utc)
        if isinstance(ts_te, int)
        else None
    )
    subscription_record.cancel_at_period_end = bool(
        stripe_sub_data.get("cancel_at_period_end", False)
    )
    subscription_record.canceled_at = (
        datetime.fromtimestamp(ts_ca, tz=timezone.utc)
        if isinstance(ts_ca, int)
        else None
    )
    subscription_record.ended_at = (
        datetime.fromtimestamp(ts_ea, tz=timezone.utc)
        if isinstance(ts_ea, int)
        else None
    )

    db.add(subscription_record)
    return subscription_record


async def _handle_subscription_lifecycle_update(
    db: AsyncSession,
    stripe_sub_data: Dict[str, Any],  # Espera um dicionário
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
        stripe_sub_data: The Stripe Subscription object from the event.
        event_type: The type of the Stripe event (e.g., "customer.subscription.updated").
        account_id_from_event: The account ID, if directly available from the event
            (e.g., from `client_reference_id` in `checkout.session.completed`).

    Raises:
        HTTPException: If critical processing steps fail (e.g., saving subscription,
                       provisioning access).
    """
    sub_id = stripe_sub_data.get("id", "N/A_SUB_ID")  # Default para logging
    logger.info(
        f"Handling Stripe event: {event_type} for Stripe Subscription ID: {sub_id}"
    )

    subscription_record = await _update_or_create_subscription_from_stripe_object(
        db, stripe_sub_data, account_id_override=account_id_from_event
    )

    if not subscription_record:
        logger.error(
            f"Failed to update or create local subscription for Stripe Sub ID {sub_id} during {event_type}. "
            "This could be due to missing account linkage or an issue with the Stripe data."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process subscription data from Stripe event {event_type}.",
        )

    if not subscription_record.account_id:  # Salvaguarda
        logger.critical(  # Usar critical pois isso não deveria acontecer
            f"Subscription record {subscription_record.id} (Stripe: {sub_id}) "
            f"is missing an account_id after update/create. This indicates a severe logic error."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error: Subscription record is missing account association after processing.",
        )

    account_id = subscription_record.account_id

    try:
        await provision_account_access(
            db=db, account_id=account_id, active_subscription=subscription_record
        )
        logger.info(
            f"Account access provisioned/updated for Account {account_id} after event {event_type}."
        )
    except ValueError as ve:
        logger.error(
            f"ValueError during access provisioning for Account {account_id} (Sub: {sub_id}): {ve}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(ve)
        )  # Se conta não for encontrada
    except Exception as e_provision:
        logger.exception(
            f"Unexpected error during access provisioning for Account {account_id} (Sub: {sub_id}) after {event_type}: {e_provision}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to provision account access due to an internal error.",
        )

    try:
        await update_clerk_user_metadata_after_subscription_change(
            db=db, account_id=account_id
        )
        logger.info(
            f"Clerk user metadata update task initiated for Account {account_id} (Sub: {sub_id}) after event {event_type}."
        )
    except Exception as e_clerk_sync:
        logger.error(
            f"Error during Clerk metadata sync for Account {account_id} (Sub: {sub_id}) after {event_type}: {e_clerk_sync}. "
            "The primary subscription update was successful."
        )


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
    checkout_session_data: Dict[str, Any] = (
        event.data.object
    )  # event.data.object é um StripeObject, que se comporta como dict
    session_id = checkout_session_data.get("id", "N/A_SESSION_ID")
    logger.info(
        f"Processing checkout.session.completed for Stripe Session ID: {session_id}"
    )

    mode = checkout_session_data.get("mode")
    if mode != "subscription":
        logger.info(
            f"Checkout session {session_id} is not for a subscription (mode: {mode}). Skipping."
        )
        return

    client_reference_id_str = checkout_session_data.get("client_reference_id")
    stripe_subscription_id = checkout_session_data.get("subscription")

    if not client_reference_id_str:
        logger.error(
            f"Checkout session {session_id} completed without client_reference_id."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing client_reference_id.",
        )
    try:
        account_id = UUID(client_reference_id_str)
    except ValueError:
        logger.error(
            f"Invalid UUID format for client_reference_id: '{client_reference_id_str}' in session {session_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_reference_id format.",
        )

    if not stripe_subscription_id:
        logger.error(
            f"Checkout session {session_id} (subscription mode) completed without a subscription ID."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing subscription ID in session.",
        )

    try:
        # stripe.Subscription.retrieve() retorna um objeto stripe.Subscription.
        # Para consistência com _update_or_create_subscription_from_stripe_object esperando um dict,
        # convertemos para dict.
        retrieved_stripe_sub_object = stripe.Subscription.retrieve(
            stripe_subscription_id
        )
        stripe_sub_data_for_handler: Dict[str, Any] = (
            retrieved_stripe_sub_object.to_dict_recursive()
        )
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} (from session {session_id}): {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe API error retrieving subscription.",
        )

    await _handle_subscription_lifecycle_update(
        db, stripe_sub_data_for_handler, event.type, account_id_from_event=account_id
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
    invoice_data: Dict[str, Any] = event.data.object
    invoice_id = invoice_data.get("id", "N/A_INVOICE_ID")
    stripe_subscription_id = invoice_data.get("subscription")

    if not stripe_subscription_id:
        logger.info(
            f"Invoice {invoice_id} payment succeeded but no subscription ID found. Skipping."
        )
        return

    logger.info(
        f"Processing invoice.payment_succeeded for Invoice ID: {invoice_id}, linked to Stripe Sub ID: {stripe_subscription_id}"
    )

    try:
        retrieved_stripe_sub_object = stripe.Subscription.retrieve(
            stripe_subscription_id
        )
        stripe_sub_data_for_handler: Dict[str, Any] = (
            retrieved_stripe_sub_object.to_dict_recursive()
        )
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} for invoice.payment_succeeded (Invoice: {invoice_id}): {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe API error retrieving subscription for invoice.",
        )

    await _handle_subscription_lifecycle_update(
        db, stripe_sub_data_for_handler, event.type
    )


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
    # event.data.object já é o objeto Subscription (um StripeObject, que se comporta como dict)
    stripe_sub_data: Dict[str, Any] = event.data.object
    sub_id = stripe_sub_data.get("id", "N/A_SUB_ID")
    logger.info(f"Processing {event.type} for Stripe Subscription ID: {sub_id}")
    # Passamos diretamente, pois _handle_subscription_lifecycle_update espera um dict-like object.
    await _handle_subscription_lifecycle_update(db, stripe_sub_data, event.type)


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
    stripe_sub_data: Dict[str, Any] = event.data.object
    sub_id = stripe_sub_data.get("id", "N/A_SUB_ID")
    logger.info(
        f"Processing customer.subscription.deleted for Stripe Subscription ID: {sub_id}"
    )
    await _handle_subscription_lifecycle_update(db, stripe_sub_data, event.type)


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
    invoice_data: Dict[str, Any] = event.data.object
    invoice_id = invoice_data.get("id", "N/A_INVOICE_ID")
    stripe_subscription_id = invoice_data.get("subscription")

    if not stripe_subscription_id:
        logger.warning(
            f"Invoice {invoice_id} payment failed but no subscription ID found. Skipping."
        )
        return

    logger.info(
        f"Processing invoice.payment_failed for Invoice ID: {invoice_id}, linked to Stripe Sub ID: {stripe_subscription_id}"
    )

    try:
        retrieved_stripe_sub_object = stripe.Subscription.retrieve(
            stripe_subscription_id
        )
        stripe_sub_data_for_handler: Dict[str, Any] = (
            retrieved_stripe_sub_object.to_dict_recursive()
        )
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} for invoice.payment_failed (Invoice: {invoice_id}): {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe API error retrieving subscription for failed invoice.",
        )

    await _handle_subscription_lifecycle_update(
        db, stripe_sub_data_for_handler, event.type
    )
