# app/services/subscription_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from loguru import logger
from uuid import UUID
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.models.account import Account
from app.models.account_user import AccountUser
from app.models.user import User
from app.core.billing_plans import STRIPE_PRODUCT_TO_PLAN_TIER, AccountPlanTierEnum
from app.models.subscription import Subscription, SubscriptionStatusEnum
from app.core.dependencies.billing import get_current_subscription_for_account
from app.config import get_settings

# Importar o SDK do Clerk
from clerk_backend_api import Clerk

# Opcional: importar tipos específicos de operações se o SDK os fornecer e você os usar
# from clerk_backend_api.models import operations

settings = get_settings()

# Instanciar o cliente Clerk uma vez se possível, ou usar context manager em cada chamada
# Se o SDK suportar uma instância global configurada:
# _clerk_client_instance = None
# def get_clerk_client():
#     global _clerk_client_instance
#     if _clerk_client_instance is None and settings.CLERK_SECRET_KEY:
#         _clerk_client_instance = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)
#     elif not settings.CLERK_SECRET_KEY:
#         logger.warning("CLERK_SECRET_KEY not set. Clerk operations will be skipped.")
#     return _clerk_client_instance


async def _update_single_clerk_user_metadata(
    clerk_uid: str,
    metadata_payload: Dict[str, Any],
    account_id_for_logging: UUID,  # Apenas para logs melhores
):
    """Helper para atualizar metadados de um único usuário Clerk."""
    if not settings.CLERK_SECRET_KEY:
        logger.warning(
            f"CLERK_SECRET_KEY not set. Skipping metadata update for Clerk user {clerk_uid}."
        )
        return False

    # Usar o context manager para cada chamada é mais seguro para gerenciamento de recursos do SDK
    async with Clerk(bearer_auth=settings.CLERK_SECRET_KEY) as clerk:
        try:
            logger.debug(
                f"Attempting to update Clerk public_metadata for user {clerk_uid} (Account {account_id_for_logging}) with: {metadata_payload}"
            )

            # Verifique a documentação do SDK para a forma exata de chamar update_metadata.
            # Pode ser clerk.users.update_metadata(...) ou clerk.users.update(...),
            # e os parâmetros podem ser diretos ou via um objeto request_body.
            # Exemplo comum:
            logger.debug(f"Updating clerk metadata: {metadata_payload}")
            response = await clerk.users.update_metadata_async(  # Ou users.update se for mais geral
                user_id=clerk_uid,
                public_metadata=metadata_payload,
                # Ou: request_body=operations.UsersUpdateMetadataRequestBody(public_metadata=metadata_payload)
            )

            # Verifique a condição de sucesso da resposta conforme a documentação do SDK
            if (
                response and hasattr(response, "id") and response.id == clerk_uid
            ):  # Exemplo de verificação
                logger.info(
                    f"Successfully updated Clerk public_metadata for user {clerk_uid} of Account {account_id_for_logging}."
                )
                return True
            else:
                logger.warning(
                    f"Clerk metadata update for user {clerk_uid} may not have succeeded as expected. Response: {response}"
                )
                return False
        except Exception as e:
            logger.error(
                f"Clerk SDK error updating metadata for user {clerk_uid} (Account {account_id_for_logging}): {e}"
            )
            return False


async def update_clerk_user_metadata_after_subscription_change(
    db: AsyncSession, account_id: UUID
):
    logger.info(f"Starting Clerk metadata update for users of Account ID: {account_id}")
    account = await db.get(Account, account_id)
    if not account:
        logger.error(f"Account {account_id} not found. Cannot update Clerk metadata.")
        return

    active_subscription = await get_current_subscription_for_account(db, account_id)

    clerk_metadata_payload: Dict[str, Any] = {
        "subscription_status": "none",
        "plan_product_id": None,
        "current_period_end": None,
        "trial_ends_at": None,
        "cancel_at_period_end": False,
    }

    if active_subscription:
        logger.debug(
            f"Account {account_id} has subscription {active_subscription.id} with status {active_subscription.status.value}"
        )
        clerk_metadata_payload["subscription_status"] = active_subscription.status.value
        clerk_metadata_payload["plan_product_id"] = (
            active_subscription.stripe_product_id
        )

        if active_subscription.current_period_end:
            clerk_metadata_payload["current_period_end"] = (
                active_subscription.current_period_end.isoformat()
            )

        if (
            active_subscription.status == SubscriptionStatusEnum.TRIALING
            and active_subscription.trial_ends_at
        ):
            clerk_metadata_payload["trial_ends_at"] = (
                active_subscription.trial_ends_at.isoformat()
            )

        clerk_metadata_payload["cancel_at_period_end"] = (
            active_subscription.cancel_at_period_end
        )
    else:
        logger.debug(
            f"Account {account_id} has no active/trialing subscription. Clerk metadata will reflect this."
        )

    stmt = (
        select(User.uid)
        .join(AccountUser, User.id == AccountUser.user_id)
        .where(AccountUser.account_id == account_id)
        .where(User.provider == "clerk")
        .where(User.uid.is_not(None))
    )
    clerk_user_ids_result = await db.execute(stmt)
    clerk_uids_to_update: List[str] = clerk_user_ids_result.scalars().all()

    if not clerk_uids_to_update:
        logger.info(
            f"No Clerk users found associated with Account ID {account_id} to update metadata."
        )
        return

    logger.info(
        f"Found Clerk UIDs to update for Account {account_id}: {clerk_uids_to_update}"
    )

    update_tasks = [
        _update_single_clerk_user_metadata(
            clerk_uid=clerk_uid,
            metadata_payload=clerk_metadata_payload,
            account_id_for_logging=account_id,
        )
        for clerk_uid in clerk_uids_to_update
    ]
    results = await asyncio.gather(
        *update_tasks, return_exceptions=True
    )  # Executar em paralelo

    for i, result in enumerate(results):
        if isinstance(result, Exception) or result is False:
            logger.error(
                f"Failed to update metadata for Clerk UID {clerk_uids_to_update[i]} (from gather). Result: {result}"
            )
        # else: logger.info(f"Successfully updated metadata for Clerk UID {clerk_uids_to_update[i]} (from gather).")


async def provision_account_access(
    db: AsyncSession,
    account_id: UUID,
    active_subscription: Optional[Subscription],  # A assinatura ATIVA ou TRIALING
):
    """
    Updates the account's plan tier based on the active subscription.
    This function should be called after a subscription status change.
    """
    account = await db.get(Account, account_id)
    if not account:
        logger.error(
            f"Account {account_id} not found during access provisioning for plan tier."
        )
        return

    new_plan_tier = (
        AccountPlanTierEnum.FREE
    )  # Default para sem assinatura ativa/trialing

    if active_subscription and active_subscription.status in [
        SubscriptionStatusEnum.ACTIVE,
        SubscriptionStatusEnum.TRIALING,
    ]:
        stripe_product_id = active_subscription.stripe_product_id
        if stripe_product_id and stripe_product_id in STRIPE_PRODUCT_TO_PLAN_TIER:
            new_plan_tier = STRIPE_PRODUCT_TO_PLAN_TIER[stripe_product_id]
            logger.info(
                f"Account {account_id}: Mapping Stripe Product ID {stripe_product_id} to Plan Tier {new_plan_tier}"
            )
        else:
            logger.warning(
                f"Account {account_id}: Stripe Product ID {stripe_product_id} from active subscription {active_subscription.id} not found in STRIPE_PRODUCT_TO_PLAN_TIER mapping. Defaulting to FREE tier."
            )
            # Você pode querer um tratamento de erro mais robusto aqui ou um plano padrão.
            new_plan_tier = AccountPlanTierEnum.FREE.value
    else:
        logger.info(
            f"Account {account_id}: No active/trialing subscription. Setting plan tier to FREE."
        )
        # new_plan_tier já é FREE

    if account.active_plan_tier != new_plan_tier:
        account.active_plan_tier = new_plan_tier
        db.add(account)  # Marcar para salvar a mudança
        logger.info(f"Account {account_id}: Plan tier updated to {new_plan_tier}.")
    else:
        logger.info(
            f"Account {account_id}: Plan tier {new_plan_tier} is already up to date."
        )
