# app/services/stripe_webhook_service.py (ou stripe_service.py)
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from sqlalchemy import select
from loguru import logger
from datetime import datetime, timezone
from typing import Optional
import stripe

from app.models.account import Account
from app.models.subscription import Subscription, SubscriptionStatusEnum
from app.database import get_db  # Para injetar db se necessário
from app.config import get_settings

settings = get_settings()


async def _update_or_create_subscription_from_stripe_object(
    db: AsyncSession,
    stripe_sub_object: stripe.Subscription,  # O objeto Subscription completo do Stripe
    account_id_override: Optional[
        UUID
    ] = None,  # Para o caso de checkout.session.completed
) -> Optional[Subscription]:
    """
    Helper para criar ou atualizar um registro de Subscription no nosso DB
    a partir de um objeto Subscription do Stripe.
    """
    logger.info(
        f"Updating/creating local subscription for Stripe Sub ID: {stripe_sub_object.id}, Status: {stripe_sub_object.status}"
    )

    # Tentar encontrar a conta. Se account_id_override for fornecido (de client_reference_id), use-o.
    # Caso contrário, tente encontrar a conta pelo stripe_customer_id.
    account_id_to_use = account_id_override
    if not account_id_to_use:
        if not stripe_sub_object.customer or not isinstance(
            stripe_sub_object.customer, str
        ):
            logger.error(
                f"Stripe Subscription {stripe_sub_object.id} is missing a valid string customer ID."
            )
            return (
                None  # Não podemos prosseguir sem um customer ID para encontrar a conta
            )

        account_stmt = select(Account).where(
            Account.stripe_customer_id == stripe_sub_object.customer
        )
        account_res = await db.execute(account_stmt)
        account = account_res.scalars().first()
        if not account:
            logger.error(
                f"No account found for Stripe Customer ID: {stripe_sub_object.customer} (from Stripe Sub {stripe_sub_object.id})"
            )
            return None  # Não podemos associar a assinatura
        account_id_to_use = account.id

    if not account_id_to_use:  # Checagem final
        logger.error(
            f"Could not determine account_id for Stripe Subscription {stripe_sub_object.id}"
        )
        return None

    # Verificar se já existe uma Subscription com este stripe_subscription_id
    sub_stmt = select(Subscription).where(
        Subscription.stripe_subscription_id == stripe_sub_object.id
    )
    existing_sub_result = await db.execute(sub_stmt)
    subscription_record = existing_sub_result.scalars().first()

    if not subscription_record:
        subscription_record = Subscription(stripe_subscription_id=stripe_sub_object.id)
        logger.info(
            f"Creating new Subscription record for stripe_subscription_id: {stripe_sub_object.id}"
        )
    else:
        logger.info(
            f"Updating existing Subscription record for stripe_subscription_id: {stripe_sub_object.id}"
        )

    subscription_record.account_id = account_id_to_use
    subscription_record.stripe_customer_id = str(
        stripe_sub_object.customer
    )  # Garantir que é string

    # Price e Product podem estar em items.data[0].price.id e .product
    if stripe_sub_object.items and stripe_sub_object.items.data:
        primary_item = stripe_sub_object.items.data[0]
        if primary_item and primary_item.price:
            subscription_record.stripe_price_id = primary_item.price.id
            if primary_item.price.product and isinstance(
                primary_item.price.product, str
            ):  # product pode ser objeto expandido ou ID string
                subscription_record.stripe_product_id = primary_item.price.product
            elif hasattr(primary_item.price.product, "id"):  # Se for objeto expandido
                subscription_record.stripe_product_id = primary_item.price.product.id  # type: ignore
    else:  # Fallback se items não estiver presente como esperado
        subscription_record.stripe_price_id = (
            stripe_sub_object.get("plan", {}).get("id")
            if stripe_sub_object.get("plan")
            else None
        )  # Legado
        if subscription_record.stripe_price_id and stripe_sub_object.get("plan"):
            subscription_record.stripe_product_id = stripe_sub_object.get(
                "plan", {}
            ).get("product")

    try:
        subscription_record.status = SubscriptionStatusEnum(stripe_sub_object.status)
    except ValueError:
        logger.warning(
            f"Unknown Stripe subscription status '{stripe_sub_object.status}' for {stripe_sub_object.id}. Defaulting to 'unpaid' or last known status."
        )
        # Manter o status anterior ou definir um padrão de erro, ex: SubscriptionStatusEnum.UNPAID
        if (
            not subscription_record.status
        ):  # Se for uma nova sub com status desconhecido
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
    subscription_record.cancel_at_period_end = stripe_sub_object.cancel_at_period_end
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
    # O commit será feito pelo chamador principal do webhook handler após todos os processamentos do evento.
    return subscription_record


async def process_checkout_session_completed(db: AsyncSession, event: stripe.Event):
    checkout_session = event.data.object
    logger.info(
        f"Processing checkout.session.completed for session ID: {checkout_session.id}"
    )

    mode = checkout_session.get("mode")
    if mode != "subscription":
        logger.info(
            f"Checkout session {checkout_session.id} is not for a subscription (mode: {mode}). Skipping."
        )
        return

    client_reference_id_str = checkout_session.get("client_reference_id")
    stripe_subscription_id = checkout_session.get("subscription")
    stripe_customer_id = checkout_session.get(
        "customer"
    )  # Pode ser string ou objeto Customer expandido

    if not client_reference_id_str:
        logger.error(
            f"Checkout session {checkout_session.id} completed without client_reference_id. Cannot associate with an account."
        )
        return

    try:
        account_id = UUID(client_reference_id_str)
    except ValueError:
        logger.error(
            f"Invalid UUID format for client_reference_id: {client_reference_id_str}"
        )
        return

    if not stripe_subscription_id:
        logger.error(
            f"Checkout session {checkout_session.id} (subscription mode) completed without a subscription ID."
        )
        return

    if (
        not stripe_customer_id
    ):  # Se customer não veio na sessão, tentar pegar da subscription
        try:
            temp_sub = stripe.Subscription.retrieve(stripe_subscription_id)
            stripe_customer_id = temp_sub.customer
        except Exception as e:
            logger.error(
                f"Failed to retrieve subscription {stripe_subscription_id} to get customer_id: {e}"
            )
            return

    if isinstance(stripe_customer_id, stripe.Customer):  # Se for objeto expandido
        stripe_customer_id = stripe_customer_id.id

    # Buscar o objeto Subscription completo do Stripe para ter todos os detalhes
    try:
        stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} during checkout completion: {e}"
        )
        # Considerar se deve levantar erro para o Stripe reenviar
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve subscription details from Stripe.",
        )

    subscription_record = await _update_or_create_subscription_from_stripe_object(
        db, stripe_sub_object, account_id_override=account_id
    )

    if subscription_record:
        # TODO: Provisionar acesso para account_id
        logger.info(
            f"Access to be provisioned for Account {account_id} based on subscription {subscription_record.id} (status: {subscription_record.status.value})"
        )
        # TODO: Atualizar metadados do Clerk
    else:
        logger.error(
            f"Failed to create/update subscription record for account {account_id} from checkout session {checkout_session.id}"
        )
        # Considerar levantar erro para o Stripe reenviar


async def process_invoice_payment_succeeded(db: AsyncSession, event: stripe.Event):
    invoice = event.data.object
    stripe_subscription_id = invoice.get("subscription")  # ID da assinatura
    stripe_customer_id = invoice.get("customer")

    logger.info(
        f"Processing invoice.payment_succeeded for invoice ID: {invoice.id}, Subscription: {stripe_subscription_id}"
    )

    if not stripe_subscription_id or not stripe_customer_id:
        logger.warning(
            f"Invoice {invoice.id} payment succeeded but missing subscription or customer ID. Skipping subscription update."
        )
        return

    try:
        stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} for invoice.payment_succeeded: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve subscription details from Stripe.",
        )

    subscription_record = await _update_or_create_subscription_from_stripe_object(
        db, stripe_sub_object
    )

    if subscription_record:
        # TODO: Garantir que o acesso está provisionado (geralmente já estaria se a sub estava ativa)
        logger.info(
            f"Access confirmed/updated for Account {subscription_record.account_id} for subscription {subscription_record.id} (status: {subscription_record.status.value})"
        )
    else:
        logger.error(
            f"Failed to update subscription record from invoice.payment_succeeded for Stripe sub {stripe_subscription_id}"
        )
        # Considerar levantar erro


async def process_customer_subscription_updated(db: AsyncSession, event: stripe.Event):
    stripe_sub_object = (
        event.data.object
    )  # O objeto Subscription já está no payload do evento
    logger.info(
        f"Processing customer.subscription.updated for Stripe Sub ID: {stripe_sub_object.id}, New Status: {stripe_sub_object.status}"
    )

    subscription_record = await _update_or_create_subscription_from_stripe_object(
        db, stripe_sub_object
    )

    if subscription_record:
        # TODO: Ajustar provisionamento de acesso com base no novo status/plano
        logger.info(
            f"Access to be re-evaluated for Account {subscription_record.account_id} for subscription {subscription_record.id} (new status: {subscription_record.status.value})"
        )
        if subscription_record.status not in [
            SubscriptionStatusEnum.ACTIVE,
            SubscriptionStatusEnum.TRIALING,
        ]:
            logger.info(
                f"Subscription {subscription_record.id} is not active/trialing. Access might need to be revoked or limited."
            )
            # Lógica para desprovisionar/limitar acesso
        else:
            logger.info(
                f"Subscription {subscription_record.id} is active/trialing. Ensuring access."
            )
            # Lógica para garantir/atualizar acesso
    else:
        logger.error(
            f"Failed to update subscription record from customer.subscription.updated for Stripe sub {stripe_sub_object.id}"
        )
        # Considerar levantar erro


async def process_customer_subscription_deleted(db: AsyncSession, event: stripe.Event):
    stripe_sub_object = event.data.object  # O objeto Subscription (cancelado)
    logger.info(
        f"Processing customer.subscription.deleted for Stripe Sub ID: {stripe_sub_object.id}"
    )

    # Mesmo que deletada, o objeto ainda tem os dados relevantes
    subscription_record = await _update_or_create_subscription_from_stripe_object(
        db, stripe_sub_object
    )

    if subscription_record:
        # O status já deve ser 'canceled' ou similar vindo do stripe_sub_object
        logger.info(
            f"Subscription {subscription_record.id} (Stripe: {stripe_sub_object.id}) for account {subscription_record.account_id} marked as {subscription_record.status.value}. Des-provisioning access."
        )
        # TODO: Desprovisionar acesso
    else:
        logger.error(
            f"Failed to update subscription record from customer.subscription.deleted for Stripe sub {stripe_sub_object.id}"
        )
        # Considerar levantar erro


async def process_invoice_payment_failed(db: AsyncSession, event: stripe.Event):
    invoice = event.data.object
    stripe_subscription_id = invoice.get("subscription")
    stripe_customer_id = invoice.get("customer")

    logger.info(
        f"Processing invoice.payment_failed for invoice ID: {invoice.id}, Subscription: {stripe_subscription_id}"
    )

    if not stripe_subscription_id or not stripe_customer_id:
        logger.warning(
            f"Invoice {invoice.id} payment failed but missing subscription or customer ID. Skipping subscription update."
        )
        return

    try:
        stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id)
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id} for invoice.payment_failed: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve subscription details from Stripe.",
        )

    subscription_record = await _update_or_create_subscription_from_stripe_object(
        db, stripe_sub_object
    )

    if subscription_record:
        # O status da subscription_record já deve ter sido atualizado para past_due ou unpaid pelo Stripe
        logger.warning(
            f"Payment failed for subscription {subscription_record.id} (Stripe: {stripe_subscription_id}). Account {subscription_record.account_id}. Status: {subscription_record.status.value}."
        )
        # TODO: Notificar usuário, iniciar processo de dunning, ou restringir acesso se o status for grave (ex: unpaid)
    else:
        logger.error(
            f"Failed to update subscription record from invoice.payment_failed for Stripe sub {stripe_subscription_id}"
        )
        # Considerar levantar erro
