# app/services/stripe_webhook_service.py (ou stripe_service.py)
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from datetime import datetime, timezone
import stripe

from app.models.account import Account
from app.models.subscription import Subscription, SubscriptionStatusEnum
from app.database import get_db  # Para injetar db se necessário
from app.config import get_settings

settings = get_settings()


async def process_checkout_session_completed(db: AsyncSession, event: stripe.Event):
    checkout_session = event.data.object
    logger.info(
        f"Processing checkout.session.completed for session ID: {checkout_session.id}"
    )

    # 1. Extrair informações relevantes
    client_reference_id = checkout_session.get(
        "client_reference_id"
    )  # Nosso account_id
    stripe_customer_id = checkout_session.get("customer")
    stripe_subscription_id = checkout_session.get("subscription")
    mode = checkout_session.get("mode")

    logger.info(
        f"Checkout session details: client_ref='{client_reference_id}', "
        f"stripe_customer_id='{stripe_customer_id}', stripe_subscription_id='{stripe_subscription_id}', "
        f"mode='{mode}'"
    )

    if mode != "subscription":
        logger.info(
            f"Checkout session {checkout_session.id} is not for a subscription (mode: {mode}). Skipping subscription processing."
        )
        return

    if not client_reference_id:
        logger.error(
            f"Checkout session {checkout_session.id} completed without client_reference_id. Cannot associate with an account."
        )
        # Em produção, isso seria um problema sério. Para testes com `stripe trigger`, é esperado.
        return

    if not stripe_subscription_id:
        logger.error(
            f"Checkout session {checkout_session.id} (subscription mode) completed without a subscription ID."
        )
        return

    if not stripe_customer_id:
        logger.error(
            f"Checkout session {checkout_session.id} (subscription mode) completed without a customer ID."
        )
        # Tentar obter do objeto subscription se disponível
        try:
            subscription_obj = stripe.Subscription.retrieve(stripe_subscription_id)
            stripe_customer_id = subscription_obj.customer
            logger.info(
                f"Retrieved customer_id '{stripe_customer_id}' from subscription '{stripe_subscription_id}'"
            )
        except Exception as e:
            logger.error(
                f"Failed to retrieve subscription {stripe_subscription_id} to get customer_id: {e}"
            )
            return
        if not stripe_customer_id:
            logger.error(
                f"Still no customer_id after attempting to retrieve from subscription {stripe_subscription_id}"
            )
            return

    # 2. Buscar a conta no nosso DB usando client_reference_id (account_id)
    from app.models.account import Account  # Import local para evitar circular
    from sqlalchemy import select

    account_stmt = select(Account).where(Account.id == client_reference_id)
    account_result = await db.execute(account_stmt)
    account = account_result.scalars().first()

    if not account:
        logger.error(
            f"Account not found for client_reference_id: {client_reference_id} from checkout session {checkout_session.id}"
        )
        return

    # 3. (Opcional, mas bom) Atualizar stripe_customer_id na nossa Account se ainda não estiver lá
    # ou se for diferente (improvável neste fluxo, mas bom para consistência)
    if (
        not account.stripe_customer_id
        or account.stripe_customer_id != stripe_customer_id
    ):
        logger.info(
            f"Updating account {account.id} with stripe_customer_id {stripe_customer_id}"
        )
        account.stripe_customer_id = stripe_customer_id
        db.add(account)
        # O commit principal será feito após salvar a Subscription

    # 4. Buscar o objeto Subscription completo do Stripe para ter todos os detalhes
    try:
        stripe_sub_object = stripe.Subscription.retrieve(stripe_subscription_id)
        logger.info(
            f"Retrieved Stripe Subscription object: {stripe_sub_object.id}, Status: {stripe_sub_object.status}"
        )
    except stripe.error.StripeError as e:
        logger.error(
            f"Failed to retrieve Stripe Subscription {stripe_subscription_id}: {e}"
        )
        return

    # 5. Criar ou Atualizar o registro Subscription no nosso banco de dados
    # Verificar se já existe uma Subscription com este stripe_subscription_id (idempotência)
    sub_stmt = select(Subscription).where(
        Subscription.stripe_subscription_id == stripe_subscription_id
    )
    existing_sub_result = await db.execute(sub_stmt)
    subscription_record = existing_sub_result.scalars().first()

    if not subscription_record:
        subscription_record = Subscription(
            stripe_subscription_id=stripe_subscription_id
        )
        logger.info(
            f"Creating new Subscription record for stripe_subscription_id: {stripe_subscription_id}"
        )
    else:
        logger.info(
            f"Updating existing Subscription record for stripe_subscription_id: {stripe_subscription_id}"
        )

    subscription_record.account_id = account.id
    subscription_record.stripe_customer_id = stripe_customer_id  # Já temos
    subscription_record.stripe_price_id = (
        stripe_sub_object.items.data[0].price.id
        if stripe_sub_object.items.data
        else None
    )
    subscription_record.stripe_product_id = (
        stripe_sub_object.items.data[0].price.product
        if stripe_sub_object.items.data
        else None
    )

    # Mapear status do Stripe para o nosso Enum
    try:
        subscription_record.status = SubscriptionStatusEnum(stripe_sub_object.status)
    except ValueError:
        logger.error(
            f"Unknown Stripe subscription status '{stripe_sub_object.status}' for {stripe_subscription_id}. Setting to unpaid or handling as error."
        )
        subscription_record.status = (
            SubscriptionStatusEnum.UNPAID
        )  # Ou um status de erro/desconhecido

    subscription_record.current_period_start = datetime.fromtimestamp(
        stripe_sub_object.current_period_start, tz=timezone.utc
    )
    subscription_record.current_period_end = datetime.fromtimestamp(
        stripe_sub_object.current_period_end, tz=timezone.utc
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

    # 6. Provisionar acesso / Lógica de Negócio
    logger.info(
        f"Subscription {subscription_record.id} (Stripe: {stripe_subscription_id}) for account {account.id} is now {subscription_record.status.value}. Provisioning access..."
    )
    # TODO: Implementar lógica de provisionamento (ex: setar um flag na Account, etc.)
    # TODO: Atualizar metadados no Clerk se necessário

    try:
        await db.commit()
        logger.info(
            f"Successfully processed checkout.session.completed for Stripe sub {stripe_subscription_id}, Our sub ID {subscription_record.id}"
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            f"DB Error processing checkout.session.completed for {stripe_subscription_id}: {e}"
        )
        # Considerar levantar uma exceção para que o Stripe tente reenviar, ou lidar com isso de outra forma
        raise  # Re-lançar para que o handler de webhook possa retornar um erro 500 para o Stripe


# Adicionar outros handlers de evento aqui
# async def process_invoice_payment_succeeded(db: AsyncSession, event: stripe.Event): ...
