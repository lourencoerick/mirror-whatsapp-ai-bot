# backend/app/core/dependencies/billing.py

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
from loguru import logger  # Coloque no topo do arquivo se não estiver lá
from datetime import datetime  # Necessário para current_period_end

from app.database import get_db
from app.core.dependencies.auth import AuthContext, get_auth_context
from app.models.subscription import Subscription, SubscriptionStatusEnum

# Account não é importado aqui diretamente, pois obtemos o account_id do AuthContext


async def get_current_subscription_for_account(
    db: AsyncSession, account_id: UUID
) -> Optional[Subscription]:
    """
    Fetches the most relevant (e.g., active or trialing) subscription for a given account_id.
    If multiple such subscriptions exist (e.g., overlapping trials or errors),
    it prioritizes the one with the latest creation date or latest period end.

    Args:
        db: The SQLAlchemy async session.
        account_id: The ID of the account to fetch the subscription for.

    Returns:
        The Subscription object if a relevant one is found, otherwise None.
    """
    logger.debug(f"Fetching current subscription for Account ID: {account_id}")
    stmt = (
        select(Subscription)
        .where(Subscription.account_id == account_id)
        .where(
            Subscription.status.in_(
                [SubscriptionStatusEnum.ACTIVE, SubscriptionStatusEnum.TRIALING]
            )
        )
        # Prioritize:
        # 1. Subscriptions ending later (longer validity)
        # 2. Subscriptions created later (newer)
        # Nulls last for current_period_end means subscriptions without an end date (e.g. some trials) might come first if not handled.
        # For active/trialing, current_period_end should ideally be set.
        .order_by(
            Subscription.current_period_end.desc().nullslast(),
            Subscription.created_at.desc(),
        )
    )

    result = await db.execute(stmt)
    subscription = result.scalars().first()

    if subscription:
        logger.info(
            f"Found relevant subscription for Account ID {account_id}: Sub ID {subscription.id}, Status {subscription.status.value}, Ends {subscription.current_period_end}"
        )
    else:
        logger.info(
            f"No active or trialing subscription found for Account ID {account_id}"
        )

    return subscription


async def require_active_subscription(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Subscription:  # Retorna o objeto Subscription ativo para possível uso na rota
    """
    FastAPI dependency that ensures the authenticated user's account has an
    active or trialing subscription.

    If a valid subscription is found, it is returned.
    Otherwise, an HTTPException (402 Payment Required) is raised.

    Args:
        auth_context: The authentication context containing the user and account.
        db: The SQLAlchemy async session.

    Returns:
        The active or trialing Subscription object.

    Raises:
        HTTPException: With status 402 if no active or trialing subscription is found.
                       With status 500 if account information is missing from auth_context.
    """
    if not auth_context.account or not auth_context.account.id:
        # Esta verificação é mais uma salvaguarda, pois get_auth_context deve garantir
        # que auth_context.account e auth_context.account.id existam.
        logger.error(
            "Account information is missing from authentication context in require_active_subscription."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication context is incomplete.",
        )

    account_id = auth_context.account.id

    active_subscription = await get_current_subscription_for_account(
        db=db, account_id=account_id
    )

    if not active_subscription:
        logger.warning(
            f"Access denied for Account ID {account_id}: No active or trialing subscription found."
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="An active subscription or trial is required to access this resource. Please check your subscription status or subscribe to a plan.",
        )

    logger.debug(
        f"Access granted for Account ID {account_id} via Subscription ID {active_subscription.id} (Status: {active_subscription.status.value})"
    )
    return active_subscription
