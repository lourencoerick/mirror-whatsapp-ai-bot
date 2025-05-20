# backend/app/services/repository/dashboard_repo.py

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import (
    select,
    func,
    and_,
    case,
    text,
)  # Adicionado text para SQL literal se necessário
from uuid import UUID
from datetime import date, datetime, timezone

from app.models.conversation import Conversation, ConversationStatusEnum
from app.models.message import Message
from app.models.inbox import Inbox
from app.api.schemas.dashboard import (
    DashboardStatsResponse,
    DashboardConversationStats,
    DashboardMessageStats,
    DashboardMessageVolumeResponse,
    MessageVolumeDatapoint,
)


# Helper para ajustar end_date para incluir o dia inteiro até 23:59:59.999999
# e garantir que está em UTC para comparações consistentes com timestamps do banco.
def _get_period_daterange(
    start_date: date, end_date: date
) -> tuple[datetime, datetime]:
    """
    Converts start and end dates to timezone-aware datetimes for a full day period.
    Start date becomes YYYY-MM-DD 00:00:00 UTC.
    End date becomes YYYY-MM-DD 23:59:59.999999 UTC.
    """
    period_start_dt = datetime.combine(
        start_date, datetime.min.time(), tzinfo=timezone.utc
    )
    period_end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
    return period_start_dt, period_end_dt


async def get_dashboard_stats(
    db: AsyncSession,
    account_id: UUID,
    start_date: date,
    end_date: date,
    inbox_id: Optional[UUID] = None,
) -> DashboardStatsResponse:
    """
    Calculates and returns various statistics for the dashboard for the given account and period.

    Args:
        db: The SQLAlchemy async session.
        account_id: The ID of the account to fetch stats for.
        start_date: The start date of the reporting period.
        end_date: The end date of the reporting period.
        inbox_id: Optional ID of an inbox to filter stats by.

    Returns:
        A DashboardStatsResponse object containing the aggregated statistics.
    """
    period_start_dt, period_end_dt = _get_period_daterange(start_date, end_date)

    # --- 1. Conversation Stats ---
    # Base query for current conversation statuses (not filtered by date period)
    current_convo_base_stmt = select(
        Conversation.status, func.count(Conversation.id).label("count")
    ).where(Conversation.account_id == account_id)
    if inbox_id:
        current_convo_base_stmt = current_convo_base_stmt.where(
            Conversation.inbox_id == inbox_id
        )

    current_convo_status_counts_result = await db.execute(
        current_convo_base_stmt.group_by(Conversation.status)
    )
    status_map = {
        row.status: row.count for row in current_convo_status_counts_result.mappings()
    }

    pending_count = status_map.get(ConversationStatusEnum.PENDING, 0)
    bot_active_count = status_map.get(ConversationStatusEnum.BOT, 0)
    human_active_count = status_map.get(ConversationStatusEnum.HUMAN_ACTIVE, 0)
    open_active_count = status_map.get(ConversationStatusEnum.OPEN, 0)
    # Note: CLOSED count here would be total closed ever, not in period.

    # Base query for conversation events within the period
    period_convo_base_stmt = select(func.count(Conversation.id)).where(
        Conversation.account_id == account_id
    )
    if inbox_id:
        period_convo_base_stmt = period_convo_base_stmt.where(
            Conversation.inbox_id == inbox_id
        )

    # New conversations in period
    new_in_period_count_result = await db.execute(
        period_convo_base_stmt.where(
            Conversation.created_at.between(period_start_dt, period_end_dt)
        )
    )
    new_in_period_count = new_in_period_count_result.scalar_one_or_none() or 0

    # Closed conversations in period
    # Assuming 'updated_at' reflects the timestamp when status changed to CLOSED
    closed_in_period_stmt = period_convo_base_stmt.where(
        Conversation.status == ConversationStatusEnum.CLOSED,
        Conversation.updated_at.between(period_start_dt, period_end_dt),
    )
    closed_in_period_count_result = await db.execute(closed_in_period_stmt)
    closed_in_period_count = closed_in_period_count_result.scalar_one_or_none() or 0

    # Placeholder for closed_by_bot and closed_by_human
    # TODO: Implement tracking for who closed the conversation (e.g., a 'closed_by_type' field in Conversation model)
    # For now, these will be 0 or require more complex logic if no model change.
    # Example if Conversation.closed_by_type exists:
    # closed_by_bot_stmt = closed_in_period_stmt.where(Conversation.closed_by_type == "bot")
    # closed_by_bot_r = await db.execute(closed_by_bot_stmt)
    # closed_by_bot_in_period_count = closed_by_bot_r.scalar_one_or_none() or 0
    closed_by_bot_in_period_count = 0
    closed_by_human_in_period_count = 0

    conversation_stats = DashboardConversationStats(
        pending_count=pending_count,
        bot_active_count=bot_active_count,
        human_active_count=human_active_count,
        open_active_count=open_active_count,
        total_active_count=bot_active_count + human_active_count + open_active_count,
        new_in_period_count=new_in_period_count,
        closed_in_period_count=closed_in_period_count,
        closed_by_bot_in_period_count=closed_by_bot_in_period_count,
        closed_by_human_in_period_count=closed_by_human_in_period_count,
    )

    # --- 2. Message Stats ---
    message_counts_stmt = (
        select(
            func.coalesce(
                func.sum(case((Message.direction == "in", 1), else_=0)), 0
            ).label("received_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Message.direction == "out",
                                Message.bot_agent_id.is_not(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("sent_by_bot_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Message.direction == "out", Message.user_id.is_not(None)
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("sent_by_human_count"),
        )
        .select_from(Message)  # Explicitly select from Message table
        .where(
            Message.account_id == account_id,
            Message.created_at.between(period_start_dt, period_end_dt),
        )
    )
    if inbox_id:
        message_counts_stmt = message_counts_stmt.where(Message.inbox_id == inbox_id)

    message_counts_result = await db.execute(message_counts_stmt)
    counts_row = (
        message_counts_result.mappings().first()
    )  # Deve retornar uma única linha com as contagens

    received_in_period_count = counts_row["received_count"] if counts_row else 0
    sent_by_bot_in_period_count = counts_row["sent_by_bot_count"] if counts_row else 0
    sent_by_human_in_period_count = (
        counts_row["sent_by_human_count"] if counts_row else 0
    )

    message_stats = DashboardMessageStats(
        received_in_period_count=received_in_period_count,
        sent_total_in_period_count=sent_by_bot_in_period_count
        + sent_by_human_in_period_count,
        sent_by_bot_in_period_count=sent_by_bot_in_period_count,
        sent_by_human_in_period_count=sent_by_human_in_period_count,
    )

    # --- 3. Active Inboxes Count ---
    # Assuming "active" means not deleted or explicitly marked inactive.
    # If no such flag, count all inboxes for the account.
    active_inboxes_stmt = select(func.count(Inbox.id)).where(
        Inbox.account_id == account_id
    )
    # Add more conditions here if 'active' has a specific meaning, e.g., Inbox.is_active == True
    active_inboxes_result = await db.execute(active_inboxes_stmt)
    active_inboxes_count = active_inboxes_result.scalar_one_or_none() or 0

    return DashboardStatsResponse(
        period_start=start_date,
        period_end=end_date,
        filtered_inbox_id=inbox_id,
        conversation_stats=conversation_stats,
        message_stats=message_stats,
        active_inboxes_count=active_inboxes_count,
    )


async def get_dashboard_message_volume(
    db: AsyncSession,
    account_id: UUID,
    start_date: date,
    end_date: date,
    granularity: str,
    inbox_id: Optional[UUID] = None,
) -> DashboardMessageVolumeResponse:
    """
    Calculates and returns message volume time series data for the dashboard.
    """
    period_start_dt, period_end_dt = _get_period_daterange(start_date, end_date)

    # Define the time grouping function based on granularity
    # This assumes PostgreSQL. Adjust for other databases if necessary.
    if granularity == "day":
        time_group_func = func.date_trunc("day", Message.created_at)
    elif granularity == "hour":
        time_group_func = func.date_trunc("hour", Message.created_at)
    else:
        # Default to day or raise an error if granularity is invalid (already checked in router)
        time_group_func = func.date_trunc("day", Message.created_at)

    # Construct the main query
    stmt = (
        select(
            time_group_func.label("timestamp_group"),
            func.coalesce(
                func.sum(case((Message.direction == "in", 1), else_=0)), 0
            ).label("received_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Message.direction == "out",
                                Message.bot_agent_id.is_not(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("sent_by_bot_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Message.direction == "out", Message.user_id.is_not(None)
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("sent_by_human_count"),
        )
        .select_from(Message)
        .where(
            Message.account_id == account_id,
            Message.created_at.between(period_start_dt, period_end_dt),
        )
        .group_by("timestamp_group")
        .order_by(text("timestamp_group asc"))
    )

    if inbox_id:
        stmt = stmt.where(Message.inbox_id == inbox_id)

    result = await db.execute(stmt)

    time_series_data: List[MessageVolumeDatapoint] = []
    for row in result.mappings():  # Use .mappings() to access columns by label
        # Ensure timestamp is timezone-aware (date_trunc usually preserves it if input is)
        ts = row["timestamp_group"]
        if (
            ts.tzinfo is None
        ):  # Defensive check, though date_trunc on timestamptz should be tz-aware
            ts = ts.replace(tzinfo=timezone.utc)

        time_series_data.append(
            MessageVolumeDatapoint(
                timestamp=ts,
                received_count=row["received_count"],
                sent_by_bot_count=row["sent_by_bot_count"],
                sent_by_human_count=row["sent_by_human_count"],
            )
        )

    # TODO: Consider filling in missing time intervals with zero counts if required by frontend charts.
    # This can be complex and might be better handled by the frontend or a dedicated time-series generation utility.

    return DashboardMessageVolumeResponse(
        period_start=start_date,
        period_end=end_date,
        filtered_inbox_id=inbox_id,
        granularity=granularity,
        time_series=time_series_data,
    )
