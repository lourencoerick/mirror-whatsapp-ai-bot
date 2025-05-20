# backend/app/api/routers/dashboard.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import date, timedelta  # Adicionado timedelta para validação de período

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.dashboard import (
    DashboardStatsResponse,
    DashboardMessageVolumeResponse,
)
from app.services.repository.dashboard import (
    get_dashboard_stats,
    get_dashboard_message_volume,
)
from app.config import (
    get_settings,
)  # Para configurações, se necessário (ex: max_period_days)

settings = get_settings()

router = APIRouter(
    prefix="/dashboard",  # Definido no nível do router principal ao incluir
    tags=["v1 - Dashboard"],
    # dependencies=[Depends(get_auth_context)] # Aplicado individualmente para clareza ou se houver rotas públicas
)

# Constante para limite máximo de período, se desejado
MAX_PERIOD_DAYS = (
    settings.DASHBOARD_MAX_PERIOD_DAYS
    if hasattr(settings, "DASHBOARD_MAX_PERIOD_DAYS")
    else 90
)


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get Dashboard Aggregated Statistics",
    description="Retrieves key performance indicators (KPIs) and aggregated counts for conversations and messages within a specified date range for the authenticated account.",
)
async def read_dashboard_stats(
    start_date: date = Query(
        ..., description="Start date for the period (YYYY-MM-DD). Example: 2023-01-01"
    ),
    end_date: date = Query(
        ..., description="End date for the period (YYYY-MM-DD). Example: 2023-01-31"
    ),
    inbox_id: Optional[UUID] = Query(
        None, description="Optional Inbox ID to filter statistics by."
    ),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DashboardStatsResponse:
    """
    Fetches aggregated statistics for the dashboard.

    - **start_date**: The beginning of the reporting period.
    - **end_date**: The end of the reporting period.
    - **inbox_id**: (Optional) Filters statistics for a specific inbox.

    The endpoint returns counts for conversation statuses (current and within the period),
    message statistics (received, sent by bot, sent by human), and the number of active inboxes.
    """
    account_id = auth_context.account.id

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date.",
        )

    if (end_date - start_date).days > MAX_PERIOD_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The reporting period cannot exceed {MAX_PERIOD_DAYS} days.",
        )

    stats = await get_dashboard_stats(
        db=db,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        inbox_id=inbox_id,
    )
    # O schema DashboardStatsResponse já foi retornado por get_dashboard_stats
    return stats


@router.get(
    "/message-volume",
    response_model=DashboardMessageVolumeResponse,
    summary="Get Message Volume Time Series",
    description="Retrieves time series data for message volume (received, sent by bot, sent by human) for the authenticated account, within a specified date range and granularity.",
)
async def read_dashboard_message_volume(
    start_date: date = Query(
        ..., description="Start date for the period (YYYY-MM-DD). Example: 2023-01-01"
    ),
    end_date: date = Query(
        ..., description="End date for the period (YYYY-MM-DD). Example: 2023-01-31"
    ),
    inbox_id: Optional[UUID] = Query(
        None, description="Optional Inbox ID to filter message volume by."
    ),
    granularity: str = Query(
        "day",
        description="Granularity of the time series data. Accepted values: 'day', 'hour'.",
        pattern="^(day|hour)$",  # Adiciona validação de regex para os valores permitidos
    ),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DashboardMessageVolumeResponse:
    """
    Fetches time series data for message volumes.

    - **start_date**: The beginning of the reporting period.
    - **end_date**: The end of the reporting period.
    - **inbox_id**: (Optional) Filters volume for a specific inbox.
    - **granularity**: Time interval for aggregation ('day' or 'hour').

    The data points include counts for received messages, messages sent by the bot,
    and messages sent by human agents for each time interval.
    """
    account_id = auth_context.account.id

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date.",
        )

    if (end_date - start_date).days > MAX_PERIOD_DAYS:
        # Para granularidade 'hour', o período pode precisar ser menor ainda.
        # Ex: se 'hour', talvez limitar a 7 dias.
        # Esta é uma validação simples, pode ser refinada.
        if granularity == "hour" and (end_date - start_date).days > 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"For 'hour' granularity, the reporting period cannot exceed 7 days.",
            )
        elif granularity == "day" and (end_date - start_date).days > MAX_PERIOD_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"For 'day' granularity, the reporting period cannot exceed {MAX_PERIOD_DAYS} days.",
            )

    # A validação de 'granularity' para 'day' ou 'hour' é feita pelo pattern no Query,
    # mas uma verificação explícita pode ser adicionada se necessário, embora o pattern seja mais eficiente.
    # if granularity not in ["day", "hour"]:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Invalid granularity. Must be 'day' or 'hour'."
    #     )

    volume_data = await get_dashboard_message_volume(
        db=db,
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        inbox_id=inbox_id,
        granularity=granularity,
    )
    # O schema DashboardMessageVolumeResponse já foi retornado por get_dashboard_message_volume
    return volume_data
