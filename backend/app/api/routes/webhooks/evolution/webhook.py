import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict
from loguru import logger

from app.database import get_db
from app.api.schemas.webhooks.evolution import EvolutionWebhookPayload
from app.api.routes.webhooks.evolution.event_handler import (
    EVENT_HANDLERS,
    handle_unknown_event,
)


router = APIRouter()


@router.post(
    "/webhooks/evolution/{platform_instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def handle_evolution_webhook(
    platform_instance_id: uuid.UUID,
    payload: EvolutionWebhookPayload = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Handles incoming webhook events from the Evolution API server.
    Dispatches events to the appropriate handler function based on the event type.
    """
    logger.info(
        f"Webhook received for instance {platform_instance_id}. Event: {payload.event}, InstanceName in Payload: {payload.instance}"
    )

    event_type = payload.event
    handler = EVENT_HANDLERS.get(event_type, handle_unknown_event)
    try:
        await handler(platform_instance_id, payload, db)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except HTTPException as http_exc:
        logger.warning(
            f"Handler raised HTTPException: {http_exc.status_code} - {http_exc.detail}"
        )
        raise http_exc

    except Exception as e:
        # For unexpected errors, log and return a generic 500 error
        logger.error(
            f"Unexpected error processing event {event_type} : {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook event.",
        )
