# backend/app/tasks/billing_tasks.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import (
    select,
    func as sql_func,
    update,
)  # Renamed func to sql_func to avoid conflict
from loguru import logger
from datetime import datetime, timezone  # Added timezone
from typing import List, Any  # For typing the result of .all()

from app.database import (
    AsyncSessionLocal,
)  # Or your way to get a DB session in the worker
from app.models.usage_event import UsageEvent
from app.services.billing.stripe_meter_service import report_usage_to_stripe_meter

# Name of the task for the ARQ scheduler
REPORT_USAGE_TASK_NAME = "report_usage_to_stripe_task"


async def report_usage_to_stripe_task(ctx: dict):  # ctx is the ARQ context
    """
    ARQ task to aggregate unreported usage events from the local database
    and send them to Stripe's Meter Events API.
    """
    task_id = ctx.get("job_id", "manual_run_report_usage")
    log_prefix = f"[{REPORT_USAGE_TASK_NAME}:{task_id}]"
    logger.info(f"{log_prefix} Starting usage reporting task to Stripe.")

    async with AsyncSessionLocal() as db:  # Ensures the DB session is properly managed
        try:
            # 1. Fetch and aggregate unreported usage
            # Group by stripe_customer_id and meter_event_name.
            # Sum the 'quantity'.
            # Get the latest 'event_timestamp' from the group to use in the Stripe report.
            # To correctly mark IDs as reported, we need them.
            # We could aggregate them into a list or perform a second query.
            # For initial simplicity, we'll focus on reporting. The update can be more extensive.
            # If exact IDs are needed: sql_func.array_agg(UsageEvent.id).label("event_ids")
            stmt_select_aggregated_usage = (
                select(
                    UsageEvent.stripe_customer_id,
                    UsageEvent.meter_event_name,
                    sql_func.sum(UsageEvent.quantity).label("total_quantity"),
                    sql_func.max(UsageEvent.event_timestamp).label(
                        "latest_event_timestamp"
                    ),
                )
                .where(UsageEvent.reported_to_stripe_at.is_(None))
                .group_by(UsageEvent.stripe_customer_id, UsageEvent.meter_event_name)
                .having(
                    sql_func.sum(UsageEvent.quantity) > 0
                )  # Only if there is quantity to report
            )

            aggregated_usage_result = await db.execute(stmt_select_aggregated_usage)
            # .all() returns a list of Row objects (which behave like named tuples)
            aggregated_usages: List[Any] = aggregated_usage_result.all()

            if not aggregated_usages:
                logger.info(f"{log_prefix} No unreported usage found to aggregate.")
                return f"{log_prefix} No usage to report."

            logger.info(
                f"{log_prefix} Found {len(aggregated_usages)} usage aggregates to report."
            )
            successful_reports = 0
            failed_reports = 0
            processed_customer_events = []  # To mark as reported

            for usage_agg_row in aggregated_usages:
                # Access by label name or index
                stripe_customer_id = usage_agg_row.stripe_customer_id
                meter_event_name = usage_agg_row.meter_event_name
                total_quantity = usage_agg_row.total_quantity
                report_timestamp = (
                    usage_agg_row.latest_event_timestamp
                )  # This is a datetime object

                logger.debug(
                    f"{log_prefix} Processing aggregate: Cust={stripe_customer_id}, "
                    f"Meter={meter_event_name}, Qty={total_quantity}, "
                    f"Timestamp={report_timestamp.isoformat()}"
                )

                # The timestamp for Stripe should be the event's (or the most recent in the aggregated batch)
                # so Stripe can assign it to the correct billing period.
                success = await report_usage_to_stripe_meter(
                    event_name=meter_event_name,
                    stripe_customer_id=stripe_customer_id,
                    value=total_quantity,
                    timestamp=report_timestamp,
                )

                if success:
                    successful_reports += 1
                    processed_customer_events.append(
                        {
                            "stripe_customer_id": stripe_customer_id,
                            "meter_event_name": meter_event_name,
                            "reported_up_to_timestamp": report_timestamp,
                            # Store the timestamp up to which events were reported for this customer/meter
                        }
                    )
                else:
                    failed_reports += 1
                    logger.error(
                        f"{log_prefix} Failed to report aggregated usage for Customer: {stripe_customer_id}, "
                        f"Meter: {meter_event_name}, Quantity: {total_quantity}"
                    )
                    # Decide whether to continue with others or stop. For now, continue.

            # 2. Mark events as reported (after reporting attempts)
            if processed_customer_events:
                logger.info(
                    f"{log_prefix} Marking {len(processed_customer_events)} event groups as reported in the DB."
                )
                for reported_info in processed_customer_events:
                    # Mark all events for this customer/meter that occurred on or before
                    # the 'latest_event_timestamp' used for the aggregated report.
                    # This avoids marking events that occurred *after* this batch was formed
                    # but *before* the reporting was completed.
                    stmt_update_reported = (
                        update(UsageEvent)
                        .where(
                            UsageEvent.stripe_customer_id
                            == reported_info["stripe_customer_id"]
                        )
                        .where(
                            UsageEvent.meter_event_name
                            == reported_info["meter_event_name"]
                        )
                        .where(UsageEvent.reported_to_stripe_at.is_(None))
                        .where(
                            UsageEvent.event_timestamp
                            <= reported_info["reported_up_to_timestamp"]
                        )
                        .values(reported_to_stripe_at=datetime.now(timezone.utc))
                    )
                    update_result = await db.execute(stmt_update_reported)
                    logger.debug(
                        f"{log_prefix} Marked {update_result.rowcount} events for "
                        f"Cust: {reported_info['stripe_customer_id']}, "
                        f"Meter: {reported_info['meter_event_name']} "
                        f"up to {reported_info['reported_up_to_timestamp'].isoformat()}"
                    )

            await db.commit()
            summary_msg = (
                f"{log_prefix} Task completed. Processed aggregates: {len(aggregated_usages)}. "
                f"Successful Stripe reports: {successful_reports}, Failures: {failed_reports}."
            )
            logger.info(summary_msg)
            return summary_msg

        except Exception as e:
            logger.exception(
                f"{log_prefix} Error during usage reporting task execution: {e}"
            )
            await db.rollback()  # Ensure rollback in case of an unhandled exception
            raise  # Re-raise so ARQ can handle (retry, dead-letter, etc.)
