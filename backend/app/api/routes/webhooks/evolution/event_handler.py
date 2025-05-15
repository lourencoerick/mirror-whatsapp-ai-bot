from uuid import UUID
from typing import Callable, Coroutine, Any, Dict, Optional
from fastapi import HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from arq.connections import ArqRedis

from app.database import get_db
from app.models.channels.evolution_instance import EvolutionInstance
from app.api.schemas.webhooks.evolution import (
    ConnectionUpdateData,
    EvolutionWebhookPayload,
)

from app.api.schemas.queue_payload import IncomingMessagePayload


from app.core.arq_manager import get_arq_pool
from app.core.wake_workers import wake_worker
from app.config import get_settings

settings = get_settings()


async def handle_connection_update(
    instance_id: UUID,
    payload: EvolutionWebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Handles the 'connection.update' event.
    Updates the instance status in the database and notifies the frontend via WebSocket.
    """
    result = await db.execute(
        select(EvolutionInstance).filter(EvolutionInstance.id == instance_id)
    )
    evolution_instance = result.scalars().first()

    if not evolution_instance:
        logger.error(f"Received connection.update for unknown instance {instance_id}.")
        return

    try:
        conn_data = ConnectionUpdateData.model_validate(payload.data)

        logger.info(
            f"Processing connection.update for instance {instance_id}. State: {conn_data.state}"
        )

        if conn_data.state == "open" and evolution_instance.status != "CONNECTED":
            logger.info(
                f"Instance {instance_id} connected (state='open'). Updating DB status."
            )
            evolution_instance.status = "CONNECTED"
            db.add(evolution_instance)
            await db.commit()
            try:
                await publish_to_instance_ws(
                    str(instance_id),
                    {
                        "type": "connection.update",
                        "payload": {
                            "instance_id": str(instance_id),
                            "status": "CONNECTED",
                        },
                    },
                )
            except Exception as e:
                logger.error(
                    f"Error publishing connection.update websocket event for {instance_id}: {e}",
                    exc_info=True,
                )

        elif conn_data.state == "close" and evolution_instance.status == "CONNECTED":
            logger.info(
                f"Instance {instance_id} disconnected (state='close'). Updating DB status."
            )
            evolution_instance.status = "DISCONNECTED"
            db.add(evolution_instance)
            await db.commit()
            try:
                await publish_to_instance_ws(
                    str(instance_id),
                    {
                        "type": "connection.update",
                        "payload": {
                            "instance_id": str(instance_id),
                            "status": "DISCONNECTED",
                        },
                    },
                )
            except Exception as e:
                logger.error(
                    f"Error publishing connection.update websocket event for {instance_id}: {e}",
                    exc_info=True,
                )

    except SQLAlchemyError as e:
        logger.error(
            f"Error processing connection.update data for {instance_id}: {e}",
            exc_info=True,
        )


async def handle_message(
    # The instance_id (UUID) should come from the path of the webhook route,
    # uniquely identifying our EvolutionInstance record.
    # The payload.instance (string) is the name from Evolution API.
    instance_id: UUID,
    payload: EvolutionWebhookPayload,
    db: AsyncSession = Depends(
        get_db
    ),  # db might not be needed if all DB ops are in ARQ task
) -> Dict[str, Any]:
    """
    Webhook to handle messages from Evolution API.
    Validates payload and enqueues it for asynchronous processing via ARQ.

    Args:
        instance_id: The internal UUID of our EvolutionInstance model,
                                  derived from the webhook path.
        payload: The validated EvolutionWebhookPayload.
        db: Async database session (may not be needed here).

    Returns:
        A dictionary indicating the message was enqueued.
    """
    log_prefix = f"[EventHandler|Msg|EvoInstanceUUID:{instance_id}]"
    logger.info(
        f"{log_prefix} Received event '{payload.event}'. Evo Instance Name from payload: {payload.instance}"
    )

    # Get ARQ client
    arq_pool: Optional[ArqRedis] = await get_arq_pool()
    if not arq_pool:
        logger.critical(
            f"{log_prefix} ARQ client (pool) is not available. Cannot enqueue webhook event."
        )
        # Return 200 to Evolution API to prevent it from disabling the webhook.
        # The message will be lost if there's no dead-letter or retry mechanism for this step.
        # This is a critical monitoring point.
        raise HTTPException(
            status_code=503,  # Service Unavailable
            detail="Message processing queue is currently unavailable. Please try again later.",
        )

    try:
        logger.debug(
            f"{log_prefix} Validated Evolution payload: {payload.model_dump_json(indent=2, exclude_none=True)}"
        )

        event = payload.event
        # The 'instance' field in the payload is the name/identifier from Evolution.
        evolution_instance_name_from_payload = payload.instance

        # We're using instance_id from the path as the primary link to our system's instance record.
        # The transformer task will use this UUID to fetch the AccountID.

        if event not in [
            "messages.upsert",
            "messages.update",
        ]:  # Expand if handling more message-like events
            logger.warning(
                f"{log_prefix} Event '{event}' is not a processable message event. Skipping."
            )
            # Return a 200 OK as we've "handled" it by ignoring it.
            return {"status": "event_ignored", "event_type": event}

        # Construct the payload for the ARQ task
        # The business_identifier for Evolution will be our internal EvolutionInstance UUID (stringified).
        # The ARQ task will use this to look up the associated account_id.
        arq_task_payload = IncomingMessagePayload(
            source_api="whatsapp_evolution",
            business_identifier=str(instance_id),
            external_raw_message=payload.model_dump(by_alias=True, exclude_none=True),
        )

        await wake_worker(settings.MESSAGE_CONSUMER_WORKER_INTERNAL_URL)
        await wake_worker(settings.AI_REPLIER_INTERNAL_URL)
        await wake_worker(settings.RESPONSE_SENDER_WORKER_INTERNAL_URL)
        # Enqueue the task
        await arq_pool.enqueue_job(
            "process_incoming_message_task",  # Name of the ARQ task function
            arq_payload_dict=arq_task_payload.model_dump(),
            _queue_name=settings.MESSAGE_PROCESSING_ARQ_QUEUE_NAME,
        )

        logger.info(
            f"{log_prefix} Enqueued event '{event}' for Evo instance name '{evolution_instance_name_from_payload}' (Our UUID: {instance_id}) for async processing."
        )

        # The source_id of the message itself is not known at this stage,
        # it will be extracted by the transformer.
        return {
            "status": "message_enqueued_for_processing",
            "event_type": event,
            "evolution_instance_name": evolution_instance_name_from_payload,
            "instance_id": str(instance_id),
        }

    except HTTPException:
        # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.exception(
            f"{log_prefix} Error while preparing to enqueue Evolution payload: {e}"
        )
        # For other errors, return a generic 500 to the client (Evolution API)
        # but log the details. The message might be lost.
        raise HTTPException(
            status_code=500, detail="Internal Server Error processing webhook."
        ) from e


async def handle_unknown_event(
    instance_id: UUID,
    payload: EvolutionWebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Handles unknown event types.
    Logs a warning message.
    """
    logger.warning(
        f"Received unhandled webhook event type '{payload.event}' for instance {instance_id}."
    )
    return {}


EVENT_HANDLERS: Dict[
    str,
    Callable[
        [UUID, EvolutionWebhookPayload, AsyncSession],
        Coroutine[Any, Any, Dict[str, Any]],
    ],
] = {
    "connection.update": handle_connection_update,
    "messages.upsert": handle_message,
}
