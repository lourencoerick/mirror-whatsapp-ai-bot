from uuid import UUID
from typing import Callable, Coroutine, Any, Dict
from fastapi import HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models.channels.evolution_instance import EvolutionInstance
from app.api.schemas.webhooks.evolution import (
    ConnectionUpdateData,
    EvolutionWebhookPayload,
)

from app.api.schemas.message import MessageCreate


from app.services.queue.iqueue import IQueue
from app.services.queue.redis_queue import RedisQueue

from app.services.helper.websocket import publish_to_instance_ws
from app.services.helper.webhook import find_account_id_from_source
from app.services.parser.parse_webhook_to_message import parse_webhook_to_message

from app.services.debounce.message_debounce import get_message_debounce_service
from app.services.queue.utils.enqueue import enqueue_ai_processing_task

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
    instance_id: UUID,
    payload: EvolutionWebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Webhook to handle messages from Evolution API (unofficial WhatsApp).
    Parses and enqueues a single message for processing.
    """
    queue: IQueue = RedisQueue(queue_name="message_queue")

    try:
        logger.debug(
            f"[webhook] Validated Evolution payload: {payload.model_dump_json(indent=2)}"
        )

        event = payload.event or ""
        logger.info(f"[webhook] Instance: {instance_id}, event {event} ")
        # instance_id = payload.data.instanceId if payload.data else None

        account_id = await find_account_id_from_source(str(instance_id), db)

        logger.info(f"[webhook] Account {account_id}, event {event} ")
        if not account_id:
            logger.warning("[webhook] Account not found for source_id")
            e = HTTPException(status_code=404, detail="Account not found for source_id")
            logger.error(f"[webhook] {e}")
            raise e
        elif event not in ["messages.upsert"]:
            logger.warning("[webhook] Not a treatable event")
            e = HTTPException(status_code=400, detail="Not a treatable event")
            logger.error(f"[webhook] {e}")
            raise e

        # try:
        #     db.execute(
        #         text("SET LOCAL my.app.account_id = :account_id"),
        #         {"account_id": str(account_id)},
        #     )
        #     logger.debug(f"[webhook] SET LOCAL my.app.account_id = {account_id}")
        # except SQLAlchemyError as e:
        #     logger.error(f"[webhook] Error setting local account_id: {e}")
        #     e = HTTPException(status_code=500, detail="Database error")
        #     raise e from e

        message: MessageCreate = await parse_webhook_to_message(
            db=db, account_id=account_id, payload=payload.model_dump()
        )

        if not message:
            e = HTTPException(status_code=400, detail="No valid message found")
            logger.error(f"[webhook] {e}")
            raise e

        await wake_worker(settings.MESSAGE_CONSUMER_WORKER_INTERNAL_URL)
        await wake_worker(settings.AI_REPLIER_INTERNAL_URL)
        await wake_worker(settings.RESPONSE_SENDER_WORKER_INTERNAL_URL)
        await queue.enqueue(message)
        logger.info(f"[webhook] Enqueued Evolution message: {message.get('source_id')}")

        # --- Caminho 2: Debounce para IA ---
        # Extrair dados necessários para o debounce service

        if message.get("direction", "") == "in":
            message_debounce_service = get_message_debounce_service()
            conversation_id_from_payload = message.get("conversation_id")
            current_message_content = message.get("content")

            if (
                not conversation_id_from_payload
            ):  # Deve ser encontrado por parse_webhook_to_message
                logger.error(
                    "[webhook:handle_message] conversation_id missing from parsed payload. Cannot proceed with debounce."
                )
                # Isso seria um erro de lógica no parse_webhook_to_message
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: conversation_id not determined",
                )

            base_payload_for_debounce = {
                "account_id": account_id,  # UUID
                "conversation_id": conversation_id_from_payload

            }

            await message_debounce_service.handle_incoming_message(
                conversation_id=conversation_id_from_payload,
                current_message_content=current_message_content,
                base_payload_for_task=base_payload_for_debounce,
                task_enqueuer_func=enqueue_ai_processing_task,
            )
            logger.info(
                f"[webhook:handle_message] Message content for conv {conversation_id_from_payload} handed to debounce service."
            )

        return {
            "status": "message enqueued",
            "source_id": message.get("source_id"),
            "conversation_id": str(message.get("conversation_id")),
        }

    except HTTPException as e:
        logger.error(f"[webhook] {e}")
        raise
    except Exception as e:
        logger.exception(f"[webhook] Error while handling Evolution payload: {e}")
        e = HTTPException(status_code=500, detail="Internal Server Error")
        logger.error(f"[webhook] {e}")
        raise e


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
