# backend/app/simulation/utils/webhook_utils.py

import asyncio
import json
import uuid
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# App Imports (ajuste os caminhos se necessário)
from app.config import get_settings
from app.api.schemas.webhooks.evolution import (  # Schema para criar o payload
    EvolutionWebhookPayload,
    EvolutionWebhookMessage,
    EvolutionWebhookData,
    EvolutionWebhookKey,
)
from app.models.message import Message  # Modelo para buscar a resposta da IA
from app.simulation.config import (  # Configs para IDs e parâmetros de polling
    SIMULATION_INBOX_ID,
    SIMULATION_CONTACT_ID,
    SIMULATION_CHANNEL_ID,
    POLL_INTERVAL_SECONDS,
    MAX_POLL_ATTEMPTS,
)

# Importar definições da persona e enums para a função de checagem
from app.simulation.schemas.persona_definition import PersonaDefinition
from app.models.simulation.simulation import SimulationOutcomeEnum
from app.models.simulation.simulation_event import SimulationEventTypeEnum


settings = get_settings()

# --- Funções Movidas e Adaptadas ---


def create_message_payload(
    message_text: str, conversation_id: Optional[UUID] = None
) -> Dict[str, Any]:
    """
    Generates an EvolutionWebhookPayload dictionary for sending a message.

    Args:
        message_text: The content of the message to send.
        conversation_id: Optional conversation ID if continuing an existing chat.

    Returns:
        A dictionary representing the JSON payload for the webhook.
    """
    # Usar IDs fixos da configuração
    account_id = SIMULATION_ACCOUNT_ID
    inbox_id = SIMULATION_INBOX_ID
    contact_id = SIMULATION_CONTACT_ID
    channel_id = SIMULATION_CHANNEL_ID
    # Gerar um ID único para esta mensagem simulada
    message_sim_id = f"sim-{uuid.uuid4()}"
    # Usar um identificador consistente para o contato simulado
    remote_jid = f"sim_contact_{contact_id}@simulated.whatsapp.net"  # Exemplo

    # Monta a estrutura do payload (baseado no seu schema EvolutionWebhookPayload)
    # Adapte conforme a estrutura exata que seu webhook espera
    payload = EvolutionWebhookPayload(
        event="messages.upsert",  # Ou o evento correto
        instance=str(channel_id),  # ID da instância/canal
        data=EvolutionWebhookData(
            key=EvolutionWebhookKey(
                remoteJid=remote_jid,
                fromMe=False,  # Mensagem da persona (simulando cliente) é recebida
                id=message_sim_id,
                participant=None,  # Ajuste se necessário
            ),
            pushName=f"sim_contact_{contact_id}",  # Nome do contato simulado
            message=EvolutionWebhookMessage(
                conversation=message_text,
                # Adicione outros campos se seu schema/parser esperar (e.g., messageContextInfo)
            ),
            messageType="conversation",  # Ou o tipo correto
            messageTimestamp=int(time.time()),  # Usar time.time() é mais simples aqui
            instanceId=str(channel_id),
            source="simulation_script",  # Identificar a origem
        ),
        # Campos adicionais que seu webhook pode esperar
        destination=f"{contact_id}@{inbox_id}",  # Exemplo de destino interno
        date_time=datetime.now(timezone.utc).isoformat(),
        server_url=settings.BACKEND_BASE_URL,  # Usar config
        apikey="simulation_key",  # Usar uma chave específica ou omitir se não aplicável
    )

    # Retorna como dicionário, excluindo Nones, pronto para JSON
    return payload.model_dump(exclude_none=True, mode="json")


async def send_message_to_webhook(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Sends a message payload to the application's webhook endpoint.

    Args:
        payload: The dictionary representing the JSON payload.

    Returns:
        The JSON response from the webhook if successful, otherwise None.
    """
    webhook_url = f"{settings.BACKEND_BASE_URL}/webhooks/evolution/{SIMULATION_CHANNEL_ID}"  # Constrói URL dinamicamente
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
                return {
                    "status": "success",
                    "conversation_id": None,
                }  # Retorna um dict padrão
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
                .where(Message.direction == "out")  # Busca mensagens de saída (da IA)
            )
            # Compara com created_at da mensagem no DB
            if last_message_timestamp:
                stmt = stmt.where(Message.created_at > last_message_timestamp)

            # Ordena pela data de criação para pegar a mais recente
            stmt = stmt.order_by(Message.created_at.desc()).limit(1)

            result = await db.execute(stmt)
            ai_message = result.scalars().first()

            if ai_message:
                logger.info(f"AI response found (DB Message ID: {ai_message.id})")
                return ai_message
        except Exception as poll_exc:
            logger.error(f"Error during DB poll for AI response: {poll_exc}")
            # Decide se continua ou para em caso de erro no poll
            # Por enquanto, continua tentando

    logger.warning(
        f"Polling timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s. No new AI response found."
    )
    return None


# --- Nova Função ---
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
                    # Map failure event to outcome
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
                    else:  # Default for other failure events like PERSONA_GAVE_UP (if logged as event)
                        return SimulationOutcomeEnum.USER_GAVE_UP
            except ValueError:
                logger.error(
                    f"Invalid event type in failure criterion: {required_event_type_str}"
                )
        # Adicione outras checagens de critério de falha aqui se necessário

    return None  # No explicit failure criterion met
