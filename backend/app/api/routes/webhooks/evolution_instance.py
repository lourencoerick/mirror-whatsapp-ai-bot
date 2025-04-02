import uuid
from loguru import logger
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, status, Body, Response
from typing import Dict

from app.database import get_db
from app.models.channels.evolution_instance import EvolutionInstance
from app.api.schemas.webhooks.evolution_instance import (
    ConnectionUpdateData,
    EvolutionInstanceWebhookPayload,
)

from app.services.helper.websocket import publish_to_instance_ws


router = APIRouter()


@router.post(
    "/webhooks/evolution/{platform_instance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def handle_evolution_webhook(
    platform_instance_id: uuid.UUID,
    payload: EvolutionInstanceWebhookPayload = Body(...),
    db: Session = Depends(get_db),
):
    """
    Handles incoming webhook events from the shared Evolution API server.
    Updates the instance status in the database based on connection events
    and prepares for handling other event types (like messages).
    """
    logger.info(
        f"Webhook received for instance {platform_instance_id}. Event: {payload.event}, InstanceName in Payload: {payload.instance}"
    )

    # 1. Find the corresponding instance in our database
    evolution_instance = (
        db.query(EvolutionInstance)
        .filter(EvolutionInstance.id == platform_instance_id)
        .first()
    )

    if not evolution_instance:
        # Instance not found in our DB. Log it but return 2xx to avoid Evolution retries.
        logger.error(
            f"Received webhook for unknown or deleted instance {platform_instance_id}. InstanceName in payload: {payload.instance}"
        )
        return {"status": "ignored", "reason": "instance_not_found"}

    # 2. Check if the instance name in the payload matches (sanity check)
    if payload.instance and payload.instance != evolution_instance.instance_name:
        logger.warning(
            f"Webhook instance name mismatch for {platform_instance_id}. Payload: '{payload.instance}', DB: '{evolution_instance.instance_name}'"
        )

    # 3. Process based on event type
    event_type = payload.event

    if event_type == "connection.update":
        try:
            # Attempt to parse the 'data' part using the specific model
            if payload.data:
                conn_data = ConnectionUpdateData.model_validate(payload.data)

                logger.info(
                    f"Processing connection.update for instance {platform_instance_id}. State: {conn_data.state}"
                )

                if (
                    conn_data.state == "open"
                    and evolution_instance.status != "CONNECTED"
                ):
                    logger.info(
                        f"Instance {platform_instance_id} connected (state='open'). Updating DB status."
                    )
                    evolution_instance.status = "CONNECTED"
                    db.add(evolution_instance)
                    db.commit()
                    # Notify frontend via WebSocket
                    await publish_to_instance_ws(
                        str(platform_instance_id),
                        {
                            "type": "connection.update",
                            "payload": {
                                "instance_id": str(platform_instance_id),
                                "status": "CONNECTED",
                            },
                        },
                    )

                elif (
                    conn_data.state == "close"
                    and evolution_instance.status == "CONNECTED"
                ):
                    logger.info(
                        f"Instance {platform_instance_id} disconnected (state='close'). Updating DB status."
                    )
                    evolution_instance.status = "DISCONNECTED"
                    db.add(evolution_instance)
                    db.commit()
                    # Notify frontend via WebSocket
                    await publish_to_instance_ws(
                        str(platform_instance_id),
                        {
                            "type": "connection.update",
                            "payload": {
                                "instance_id": str(platform_instance_id),
                                "status": "DISCONNECTED",
                            },
                        },
                    )

            else:
                logger.warning(
                    f"Received connection.update event for {platform_instance_id} but 'data' field is missing or null."
                )

        except Exception as e:
            logger.error(
                f"Error processing connection.update data for {platform_instance_id}: {e}",
                exc_info=True,
            )
            # Don't raise HTTPException, just log and acknowledge receipt

    else:
        logger.debug(
            f"Received unhandled webhook event type '{event_type}' for instance {platform_instance_id}."
        )
    # 4. Acknowledge receipt to Evolution API
    # Return 204 No Content to indicate successful processing without needing to send a body back
    return Response(status_code=status.HTTP_204_NO_CONTENT)
