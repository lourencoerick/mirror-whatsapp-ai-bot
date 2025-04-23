import asyncio
import json
import uuid
import time
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.api.schemas.webhooks.evolution import (
    EvolutionWebhookPayload,
    EvolutionWebhookMessage,
    EvolutionWebhookData,
    EvolutionWebhookKey,
)
from app.models.message import Message
from app.simulation.config import (
    SIMULATION_ACCOUNT_ID,
    SIMULATION_INBOX_ID,
    SIMULATION_CONTACT_ID,
    SIMULATION_CHANNEL_ID,
    POLL_INTERVAL_SECONDS,
    MAX_POLL_ATTEMPTS,
    WEBHOOK_URL,
)
from app.simulation.schemas.persona_definition import PersonaDefinition
from app.models.simulation.simulation import SimulationOutcomeEnum
from app.models.simulation.simulation_event import SimulationEventTypeEnum

settings = get_settings()


def create_message_payload(
    message_text: str, identifier: str, conversation_id: Optional[UUID] = None
) -> Dict[str, Any]:
    """
    Generates an EvolutionWebhookPayload dictionary for sending a message.

    Args:
        message_text: The content of the message to send.
        identifier: The unique identifier of the simulated contact.
        conversation_id: Optional conversation ID for continuing an existing chat.

    Returns:
        A dictionary representing the JSON payload for the webhook.
    """
    account_id = SIMULATION_ACCOUNT_ID
    inbox_id = SIMULATION_INBOX_ID
    contact_id = SIMULATION_CONTACT_ID
    channel_id = SIMULATION_CHANNEL_ID

    message_sim_id = f"sim-{uuid.uuid4()}"
    remote_jid = f"{identifier}@simulated.whatsapp.net"

    current_epoch_timestamp = int(time.time())

    payload = EvolutionWebhookPayload(
        event="messages.upsert",
        instance=channel_id,
        data=EvolutionWebhookData(
            key=EvolutionWebhookKey(
                remoteJid=remote_jid,
                fromMe=False,
                id=message_sim_id,
            ),
            pushName=f"sim_contact_{contact_id}",
            message=EvolutionWebhookMessage(conversation=message_text),
            messageType="conversation",
            messageTimestamp=current_epoch_timestamp,
            instanceId=channel_id,
            source="sim-evolution",
        ),
        destination=f"{SIMULATION_CONTACT_ID}@{SIMULATION_INBOX_ID}",
        date_time=datetime.now(timezone.utc).isoformat(),
        server_url="sim-server-url",
        apikey="sim-api-key",
    )

    return payload.model_dump(exclude_none=True, mode="json")


async def send_message_to_webhook(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Sends a message payload to the application's webhook endpoint.

    Args:
        payload: The dictionary representing the JSON payload.

    Returns:
        The JSON response from the webhook if successful, otherwise None.
    """
    webhook_url = WEBHOOK_URL
    logger.debug(f"Sending payload to webhook: {webhook_url}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(webhook_url, json=payload, timeout=30.0)
            response.raise_for_status()
            logger.info(
                f"Webhook received message successfully (Status: {response.status_code})"
            )
            logger.debug(f"Webhook response text: {response.text}")
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.warning("Webhook response was not valid JSON.")
                return {"status": "success", "conversation_id": None}
        except httpx.RequestError as exc:
            logger.error(f"HTTP Request error sending to webhook: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            logger.error(
                f"HTTP Status error sending to webhook: {exc.response.status_code} - {exc.response.text}"
            )
            return None
        except Exception as e:
            logger.exception(f"Unexpected error sending to webhook: {e}")
            return None


async def poll_for_ai_response(
    db: AsyncSession, conversation_id: UUID, last_message_timestamp: Optional[datetime]
) -> Optional[Message]:
    """
    Polls the database for a new AI response ('out' direction) in the conversation
    that was created after a specific timestamp.

    Args:
        db: The SQLAlchemy async session.
        conversation_id: The ID of the conversation to poll.
        last_message_timestamp: Timestamp after which to look for new messages.

    Returns:
        The latest AI Message object found, or None if timed out.
    """
    logger.debug(
        f"Polling for AI response in conversation {conversation_id} after {last_message_timestamp}..."
    )
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        logger.debug(f"Polling attempt {attempt + 1}/{MAX_POLL_ATTEMPTS}...")
        try:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .where(Message.direction == "out")  # Fetching outgoing messages
            )
            if last_message_timestamp:
                stmt = stmt.where(Message.created_at > last_message_timestamp)

            stmt = stmt.order_by(Message.created_at.desc()).limit(1)

            result = await db.execute(stmt)
            ai_message = result.scalars().first()

            if ai_message:
                logger.info(f"AI response found (DB Message ID: {ai_message.id})")
                return ai_message
        except Exception as poll_exc:
            logger.error(f"Error during DB poll for AI response: {poll_exc}")

    logger.warning(
        f"Polling timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s. No new AI response found."
    )
    return None


def check_explicit_failure_criteria(
    persona: PersonaDefinition,
    turn: int,
    events_occurred: List[SimulationEventTypeEnum],
) -> Optional[SimulationOutcomeEnum]:
    """
    Checks explicit failure criteria defined in the persona.

    Args:
        persona: The PersonaDefinition object.
        turn: The current turn number.
        events_occurred: A list of event types that occurred in this run.

    Returns:
        The SimulationOutcomeEnum if a failure criterion is met, otherwise None.
    """
    for criterion in persona.failure_criteria:
        if criterion.startswith("turn_count > "):
            try:
                limit = int(criterion.split(" > ")[1])
                if turn > limit:
                    logger.warning(
                        f"Failure criterion met: Turn count {turn} exceeded limit {limit}."
                    )
                    return SimulationOutcomeEnum.TURN_LIMIT_REACHED
            except (ValueError, IndexError):
                logger.error(f"Invalid turn_count criterion format: {criterion}")
        elif criterion.startswith("event:"):
            required_event_type_str = criterion.split(":", 1)[1]
            try:
                required_event_type = SimulationEventTypeEnum(required_event_type_str)
                if required_event_type in events_occurred:
                    logger.warning(
                        f"Failure criterion met: Event '{required_event_type.value}' occurred."
                    )
                    if (
                        required_event_type
                        == SimulationEventTypeEnum.AI_FALLBACK_DETECTED
                    ):
                        return SimulationOutcomeEnum.AI_USED_FALLBACK
                    elif (
                        required_event_type
                        == SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    ):
                        return SimulationOutcomeEnum.SIMULATION_ERROR
                    elif (
                        required_event_type
                        == SimulationEventTypeEnum.AI_PROCESSING_ERROR
                    ):
                        return SimulationOutcomeEnum.AI_ERROR
                    else:
                        return SimulationOutcomeEnum.USER_GAVE_UP
            except ValueError:
                logger.error(
                    f"Invalid event type in failure criterion: {required_event_type_str}"
                )
    return None  # No explicit failure criterion met
