# backend/scripts/run_simulation.py

import asyncio
import json
import os
import sys
import uuid
import time
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

import httpx
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import numpy as np  # ADDED: Import numpy

# --- Setup sys.path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------

# --- App Imports ---
from app.database import AsyncSessionLocal

# Modelos
from app.models.simulation.simulation import (
    Simulation,
    SimulationStatusEnum,
    SimulationOutcomeEnum,
)
from app.models.simulation.simulation_message import (
    SimulationMessage,
    SimulationMessageRoleEnum,
)
from app.models.simulation.simulation_event import (
    SimulationEvent,
    SimulationEventTypeEnum,
)
from app.models.message import Message

# Schemas
from app.api.schemas.persona_definition import PersonaDefinition, ResponseTrigger
from app.api.schemas.webhooks.evolution import (
    EvolutionWebhookPayload,
    EvolutionWebhookMessage,
    EvolutionWebhookData,
    EvolutionWebhookKey,
)

# Repos
from app.services.repository import company_profile as profile_repo
from app.services.repository import message as message_repo

# Config
from app.core.simulation.config import (
    SIMULATION_ACCOUNT_ID,
    SIMULATION_INBOX_ID,
    SIMULATION_CONTACT_ID,
    SIMULATION_CHANNEL_ID,
)

from app.config import get_settings, Settings

settings: Settings = get_settings()

# --- MODIFIED: Import from embedding_utils ---
from core.simulation.embedding_utils import (
    get_embedding,
    get_embeddings_batch,
    calculate_cosine_similarity,
    EMBEDDING_PROVIDER,
)

# --- Configuration ---
PERSONA_DIR = os.path.join(project_root, "data/personas")
WEBHOOK_URL = os.getenv(
    "SIMULATION_WEBHOOK_URL",
    f"{settings.BACKEND_BASE_URL}/webhooks/evolution/{SIMULATION_CHANNEL_ID}",
)
POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 20
MAX_CONVERSATION_TURNS = 15

# --- Helper Functions ---


async def load_persona(persona_id: str) -> Optional[PersonaDefinition]:
    """Loads persona and pre-computes trigger embeddings using configured provider."""
    persona_filename = f"{persona_id}.json"
    persona_path = os.path.join(PERSONA_DIR, persona_filename)
    logger.info(f"Loading persona '{persona_id}' from {persona_path}")
    try:
        with open(persona_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        trigger_phrases = [
            trigger["semantic_trigger_phrase"]
            for trigger in data.get("response_triggers", [])
            if "semantic_trigger_phrase" in trigger
        ]
        if trigger_phrases:
            logger.debug(
                f"Getting embeddings for {len(trigger_phrases)} triggers using '{EMBEDDING_PROVIDER}' provider..."
            )
            trigger_embeddings = get_embeddings_batch(
                trigger_phrases
            )  # Returns list of np.ndarray or None

            if trigger_embeddings is None:
                logger.error(
                    "Failed to get embeddings for triggers. Persona response logic might fail."
                )
                # Decide how to handle: proceed without embeddings or abort? For now, proceed.
                for trigger in data.get("response_triggers", []):
                    trigger["embedding"] = None  # Mark as unavailable
            elif len(trigger_embeddings) == len(trigger_phrases):
                # Assign embeddings back to the triggers
                for i, trigger in enumerate(data.get("response_triggers", [])):
                    if (
                        "semantic_trigger_phrase" in trigger
                    ):  # Ensure mapping is correct
                        trigger["embedding"] = trigger_embeddings[i]
                logger.debug("Trigger embeddings computed and assigned.")
            else:
                logger.error(
                    "Mismatch between number of trigger phrases and embeddings received."
                )
                for trigger in data.get("response_triggers", []):
                    trigger["embedding"] = None  # Mark as unavailable

        persona = PersonaDefinition.model_validate(data)
        logger.success(f"Persona '{persona_id}' loaded successfully.")
        return persona

    except FileNotFoundError:
        logger.error(f"Persona file not found: {persona_path}")
        return None
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from {persona_path}")
        return None
    except ValidationError as e:
        logger.error(f"Persona validation failed for {persona_path}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error loading persona {persona_id}: {e}")
        return None


# create_initial_simulation_record, log_event, log_message, send_message unchanged...
async def create_initial_simulation_record(
    db: AsyncSession, profile_id: UUID, persona_def: PersonaDefinition
) -> Simulation:
    logger.info(
        f"Creating initial simulation record for persona '{persona_def.persona_id}'"
    )
    persona_data_to_save = persona_def.model_dump()
    if "response_triggers" in persona_data_to_save:
        for trigger in persona_data_to_save["response_triggers"]:
            trigger.pop("embedding", None)
    simulation = Simulation(
        company_profile_id=profile_id,
        persona_definition=persona_data_to_save,
        status=SimulationStatusEnum.RUNNING,
    )
    db.add(simulation)
    await db.flush()
    await db.refresh(simulation)
    logger.success(f"Simulation record created with ID: {simulation.id}")
    return simulation


async def log_simulation_event(
    db: AsyncSession,
    simulation_id: UUID,
    event_type: SimulationEventTypeEnum,
    turn: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
):
    event = SimulationEvent(
        simulation_id=simulation_id,
        event_type=event_type,
        turn_number=turn,
        details=details,
    )
    db.add(event)
    await db.flush()


async def log_simulation_message(
    db: AsyncSession,
    simulation_id: UUID,
    turn: int,
    role: SimulationMessageRoleEnum,
    content: str,
):
    message = SimulationMessage(
        simulation_id=simulation_id, turn_number=turn, role=role, content=content
    )
    db.add(message)
    await db.flush()


async def send_message_to_webhook(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    logger.debug(f"Sending payload to webhook: {WEBHOOK_URL}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(WEBHOOK_URL, json=payload, timeout=30.0)
            response.raise_for_status()
            logger.info(
                f"Webhook received message successfully (Status: {response.status_code})"
            )
            try:
                return response.json()
            except json.JSONDecodeError:
                logger.warning("Webhook response was not valid JSON.")
                return None
        except httpx.RequestError as exc:
            logger.error(f"HTTP Request error sending to webhook: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            logger.error(
                f"HTTP Status error sending to webhook: {exc.response.status_code} - {exc.response.text}"
            )
            return None


# poll_for_ai_response unchanged...
async def poll_for_ai_response(
    db: AsyncSession, conversation_id: UUID, last_message_timestamp: Optional[datetime]
) -> Optional[Message]:
    logger.debug(
        f"Polling for AI response in conversation {conversation_id} after {last_message_timestamp}..."
    )
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        logger.debug(f"Polling attempt {attempt + 1}/{MAX_POLL_ATTEMPTS}...")
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.direction == "out")
        )
        if last_message_timestamp:
            stmt = stmt.where(Message.created_at > last_message_timestamp)
        stmt = stmt.order_by(Message.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        ai_message = result.scalars().first()
        if ai_message:
            logger.info(f"AI response found (ID: {ai_message.id})")
            return ai_message
    logger.warning(
        f"Polling timed out after {MAX_POLL_ATTEMPTS} attempts. No AI response found."
    )
    return None


# --- MODIFIED: get_persona_response uses embedding_utils ---
def get_persona_response(persona: PersonaDefinition, ai_response_text: str) -> str:
    """Determines the persona's next response based on semantic similarity using configured provider."""
    logger.debug("Calculating persona response based on similarity...")
    if not ai_response_text:
        return persona.default_response

    # Get AI response embedding using the utility function
    ai_embedding = get_embedding(ai_response_text)
    if ai_embedding is None:
        logger.error(
            "Failed to get embedding for AI response. Using default persona response."
        )
        return persona.default_response

    best_match_response = persona.default_response
    highest_similarity = -1.0

    for trigger in persona.response_triggers:
        # Check if pre-computed embedding exists and is valid
        trigger_embedding = trigger.get("embedding")
        if trigger_embedding is None or not isinstance(trigger_embedding, np.ndarray):
            logger.warning(
                f"Trigger '{trigger.semantic_trigger_phrase}' has invalid or missing embedding. Skipping."
            )
            continue

        # Calculate similarity using the utility function
        similarity = calculate_cosine_similarity(ai_embedding, trigger_embedding)
        logger.debug(
            f"Similarity with trigger '{trigger.semantic_trigger_phrase}': {similarity:.4f} (Threshold: {trigger.similarity_threshold})"
        )

        if (
            similarity > trigger.similarity_threshold
            and similarity > highest_similarity
        ):
            highest_similarity = similarity
            best_match_response = trigger.persona_response
            logger.info(
                f"Best match trigger found: '{trigger.semantic_trigger_phrase}' with similarity {similarity:.4f}"
            )

    logger.debug(f"Persona response chosen: '{best_match_response}'")
    return best_match_response


# --- END MODIFICATION ---


# --- Main Simulation Logic (run_single_simulation) ---
# The main logic inside run_single_simulation remains largely the same,
# as the embedding details are now abstracted into load_persona and get_persona_response.
# Ensure error handling around persona loading/embedding generation is robust.
async def run_single_simulation(persona_id: str):
    account_id = SIMULATION_ACCOUNT_ID
    inbox_id = SIMULATION_INBOX_ID
    contact_id = SIMULATION_CONTACT_ID
    channel_id = SIMULATION_CHANNEL_ID
    logger.info(
        f"--- Starting Simulation for Account: {account_id}, Persona: {persona_id} ---"
    )
    start_time = time.time()
    simulation: Optional[Simulation] = None
    final_outcome: SimulationOutcomeEnum = SimulationOutcomeEnum.SIMULATION_ERROR
    final_status: SimulationStatusEnum = SimulationStatusEnum.FAILED
    error_msg: Optional[str] = "Simulation did not complete loop."
    turn = 0

    async with AsyncSessionLocal() as db:
        try:
            profile = await profile_repo.get_profile_by_account_id(db, account_id)
            if not profile:
                raise ValueError(f"Company profile not found for account {account_id}")

            persona = await load_persona(
                persona_id
            )  # This now handles embedding pre-computation
            if not persona:
                raise ValueError(
                    f"Persona definition '{persona_id}' not found or invalid"
                )
            # Optional: Check if embeddings were successfully computed for triggers
            if any(t.get("embedding") is None for t in persona.response_triggers):
                logger.warning(
                    "Some persona triggers are missing embeddings. Similarity matching may be incomplete."
                )

            simulation = await create_initial_simulation_record(db, profile.id, persona)
            await log_simulation_event(
                db, simulation.id, SimulationEventTypeEnum.SIMULATION_START
            )

            turn = 1
            await log_simulation_event(
                db, simulation.id, SimulationEventTypeEnum.TURN_START, turn=turn
            )

            # --- Initial Message to Webhook ---
            initial_payload = EvolutionWebhookPayload(
                event="messages.upsert",
                instance=channel_id,
                data=EvolutionWebhookData(
                    key=EvolutionWebhookKey(
                        remoteJid=f"{contact_id}@{inbox_id}",
                        fromMe=False,
                        id=f"sim-{uuid.uuid4()}",
                    ),
                    pushName=f"sim_contact_{contact_id}",
                    message=EvolutionWebhookMessage(
                        conversation=persona.initial_message
                    ),
                    messageType="conversation",
                    messageTimestamp=int(asyncio.get_event_loop().time()),
                    instanceId=channel_id,
                    source="sim-evolution",
                ),
                destination=f"{contact_id}@{inbox_id}",
                date_time=datetime.now(timezone.utc).isoformat(),
                server_url="sim-server-url",
                apikey="sim-api-key",
            )

            webhook_response = await send_message_to_webhook(initial_payload)
            if webhook_response is None:
                raise Exception("Failed to send initial message to webhook.")

            conversation_id_str = webhook_response.get(
                "conversation_id"
            )  # Adjust key if needed
            if not conversation_id_str:
                raise Exception(
                    "Could not determine conversation_id from webhook response."
                )
            conversation_id = UUID(conversation_id_str)
            logger.info(f"Obtained conversation_id: {conversation_id}")

            await log_simulation_message(
                db,
                simulation.id,
                turn=turn,
                role=SimulationMessageRoleEnum.USER,
                content=persona.initial_message,
            )
            await log_simulation_event(
                db,
                simulation.id,
                SimulationEventTypeEnum.USER_MESSAGE_SENT,
                turn=turn,
                details={"content": persona.initial_message},
            )
            last_message_time = datetime.now(timezone.utc)

            # --- Conversation Loop ---
            while turn < MAX_CONVERSATION_TURNS:
                ai_db_message = await poll_for_ai_response(
                    db, conversation_id, last_message_time
                )
                if ai_db_message is None:
                    final_outcome = SimulationOutcomeEnum.TIMEOUT
                    error_msg = "Timeout waiting for AI response."
                    await log_simulation_event(
                        db,
                        simulation.id,
                        SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    break

                ai_response_text = ai_db_message.content or ""
                last_message_time = ai_db_message.created_at

                await log_simulation_message(
                    db,
                    simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.ASSISTANT,
                    content=ai_response_text,
                )
                await log_simulation_event(
                    db,
                    simulation.id,
                    SimulationEventTypeEnum.AI_RESPONSE_RECEIVED,
                    turn=turn,
                    details={"content": ai_response_text},
                )

                # Check for AI Fallback
                if (
                    profile.fallback_contact_info
                    and profile.fallback_contact_info in ai_response_text
                ):
                    await log_simulation_event(
                        db,
                        simulation.id,
                        SimulationEventTypeEnum.AI_FALLBACK_DETECTED,
                        turn=turn,
                    )
                    if "event:AI_USED_FALLBACK" in persona.failure_criteria:
                        final_outcome = SimulationOutcomeEnum.AI_USED_FALLBACK
                        error_msg = "AI used fallback message."
                        break

                # Get Persona's Next Response using abstracted embedding logic
                persona_next_message = get_persona_response(persona, ai_response_text)

                # TODO: Implement Persona Termination Conditions Check
                # if check_termination(persona, persona_next_message, turn): break

                turn += 1
                await log_simulation_event(
                    db, simulation.id, SimulationEventTypeEnum.TURN_START, turn=turn
                )

                await log_simulation_message(
                    db,
                    simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.USER,
                    content=persona_next_message,
                )
                await log_simulation_event(
                    db,
                    simulation.id,
                    SimulationEventTypeEnum.USER_MESSAGE_SENT,
                    turn=turn,
                    details={"content": persona_next_message},
                )

                next_payload = EvolutionWebhookPayload(
                    event="messages.upsert",
                    instance=channel_id,
                    data=EvolutionWebhookData(
                        key=EvolutionWebhookKey(
                            remoteJid=f"{contact_id}@{inbox_id}",
                            fromMe=False,
                            id=f"sim-{uuid.uuid4()}",
                        ),
                        pushName=f"sim_contact_{contact_id}",
                        message=EvolutionWebhookMessage(
                            conversation=persona_next_message
                        ),
                        messageType="conversation",
                        messageTimestamp=int(asyncio.get_event_loop().time()),
                        instanceId=channel_id,
                        source="sim-evolution",
                    ),
                    destination=f"{contact_id}@{inbox_id}",
                    date_time=datetime.now(timezone.utc).isoformat(),
                    server_url="sim-server-url",
                    apikey="sim-api-key",
                )

                webhook_response = await send_message_to_webhook(next_payload)
                if webhook_response is None:
                    final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
                    error_msg = "Webhook send failed during conversation."
                    await log_simulation_event(
                        db,
                        simulation.id,
                        SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    break

            # --- End of Loop ---
            if (
                turn >= MAX_CONVERSATION_TURNS
                and simulation.status == SimulationStatusEnum.RUNNING
            ):
                final_outcome = SimulationOutcomeEnum.TURN_LIMIT_REACHED
                error_msg = f"Reached max turn limit ({MAX_CONVERSATION_TURNS})."
                await log_simulation_event(
                    db,
                    simulation.id,
                    SimulationEventTypeEnum.TURN_LIMIT_WARNING,
                    turn=turn,
                )

            if simulation.status == SimulationStatusEnum.RUNNING:
                final_status = SimulationStatusEnum.COMPLETED
                if (
                    final_outcome == SimulationOutcomeEnum.SIMULATION_ERROR
                ):  # Check if not set by loop logic
                    final_outcome = (
                        SimulationOutcomeEnum.TURN_LIMIT_REACHED
                    )  # Default completion outcome
            else:
                final_status = SimulationStatusEnum.FAILED

        except Exception as e:
            logger.exception(f"Exception during simulation run: {e}")
            final_status = SimulationStatusEnum.FAILED
            final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
            error_msg = str(e)
            if simulation:
                await log_simulation_event(
                    db,
                    simulation.id,
                    SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR,
                    turn=turn,
                    details={"error": error_msg},
                )

        finally:
            if simulation:
                end_time = time.time()
                duration = int(end_time - start_time)
                simulation.status = final_status
                simulation.outcome = final_outcome
                simulation.error_message = (
                    error_msg if final_status == SimulationStatusEnum.FAILED else None
                )
                simulation.turn_count = turn
                simulation.simulation_duration_seconds = duration
                await log_simulation_event(
                    db,
                    simulation.id,
                    SimulationEventTypeEnum.SIMULATION_END,
                    turn=turn,
                    details={"final_outcome": str(final_outcome)},
                )
                await db.commit()
                logger.info(
                    f"Simulation {simulation.id} finished with Status: {final_status}, Outcome: {final_outcome}, Duration: {duration}s"
                )
            else:
                logger.error("Simulation failed before record could be created.")

    logger.info(
        f"--- Simulation Finished for Account: {account_id}, Persona: {persona_id} ---"
    )


async def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_simulation.py <persona_id>")
        sys.exit(1)
    persona_id = sys.argv[1]
    await run_single_simulation(persona_id)


if __name__ == "__main__":
    logger.add(sys.stderr, level="INFO")
    # Ensure OpenAI API key is set if using OpenAI provider
    if EMBEDDING_PROVIDER == "openai" and not os.getenv("OPENAI_API_KEY"):
        logger.error(
            "OpenAI API key not found in environment variables (OPENAI_API_KEY)."
        )
        sys.exit(1)
    asyncio.run(main())
