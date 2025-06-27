# backend/app/api/routers/integrations/google_sheets.py

from fastapi import APIRouter, Depends, status
from loguru import logger
from arq.connections import ArqRedis

from app.api.schemas.integrations.google_sheets import SheetsTriggerPayload
from app.api.schemas.queue_payload import IncomingMessagePayload
from app.core.dependencies.api_auth import require_scope
from app.core.arq_manager import (
    get_arq_pool,
)
from app.config import get_settings, Settings
from app.models import Inbox

settings: Settings = get_settings()


# Create a new router for sheet integrations
router = APIRouter(prefix="/integrations", tags=["v1 - Integrations"])

# Define the scope required for this endpoint
SHEETS_TRIGGER_SCOPE = "sheets:trigger"


@router.post(
    "/sheets/trigger-conversation",
    summary="Accept and Enqueue a Trigger from Google Sheets",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_from_sheets(
    payload: SheetsTriggerPayload,
    current_inbox: Inbox = Depends(require_scope(SHEETS_TRIGGER_SCOPE)),
    arq_pool: ArqRedis = Depends(get_arq_pool),
):
    """
    Receives a webhook from a configured Google Sheet, validates it,
    and enqueues a task for asynchronous processing.
    """
    logger.info(
        f"Accepted Sheets trigger for Inbox '{current_inbox.name}'. Enqueuing task."
    )

    # 1. Construir o payload para a fila ARQ
    #    Este payload será recebido pelo nosso worker 'process_incoming_message_task'
    arq_payload = IncomingMessagePayload(
        source_api="integration_trigger",
        business_identifier=str(current_inbox.id),
        external_raw_message={},
        integration_trigger_payload=payload,
    )

    # 2. Enfileirar a tarefa para o worker
    await arq_pool.enqueue_job(
        "process_incoming_message_task",
        arq_payload.model_dump(mode="json"),
        _queue_name=settings.MESSAGE_QUEUE_NAME,
    )

    logger.info(
        f"Task for Inbox '{current_inbox.name}' successfully enqueued. "
        f"Contact: {payload.contact_phone}"
    )

    return {
        "status": "enqueued",
        "detail": "Trigger accepted and queued for processing.",
    }
