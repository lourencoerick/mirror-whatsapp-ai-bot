# backend/app/simulation/runner.py

import asyncio
import time
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# App Imports
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
from app.simulation.schemas.persona_definition import PersonaDefinition
from app.simulation.schemas.persona_state import (
    PersonaState,
)  # ADDED: Import PersonaState

# Repos
from app.services.repository import company_profile as profile_repo
from app.services.repository import message as message_repo

# ADDED: Simulation Repos (Opcional, mas recomendado)
from app.simulation.repositories import (
    simulation_repo,
    simulation_message_repo,
    simulation_event_repo,
)

# Persona Logic & Loader
from app.simulation.personas import loader as persona_loader  # ADDED
from app.simulation.personas import logic as persona_logic  # ADDED

# Config
from app.simulation.config import (  # ADDED: Import fixed IDs and params
    SIMULATION_ACCOUNT_ID,
    SIMULATION_INBOX_ID,
    SIMULATION_CONTACT_ID,
    POLL_INTERVAL_SECONDS,
    MAX_POLL_ATTEMPTS,
    MAX_CONVERSATION_TURNS,
)

# Utils (assumindo que send_message_to_webhook e create_message_payload foram movidos)
from app.simulation.utils import webhook_utils  # ADDED

# --- Main Simulation Logic ---


async def run_single_simulation(persona_id: str):
    """
    Orchestrates and runs a single simulation instance using the LLM Extractor approach.
    """
    account_id = SIMULATION_ACCOUNT_ID
    # inbox_id = SIMULATION_INBOX_ID # Usado dentro do payload
    # contact_id = SIMULATION_CONTACT_ID # Usado dentro do payload

    logger.info(
        f"--- Starting Simulation for Account: {account_id}, Persona: {persona_id} ---"
    )
    start_time = time.time()
    simulation: Optional[Simulation] = None
    final_outcome: SimulationOutcomeEnum = SimulationOutcomeEnum.SIMULATION_ERROR
    final_status: SimulationStatusEnum = SimulationStatusEnum.FAILED
    error_msg: Optional[str] = "Simulation did not complete loop."
    turn = 0
    events_occurred: List[SimulationEventTypeEnum] = []
    conversation_id: Optional[UUID] = None  # Initialize conversation_id

    async with AsyncSessionLocal() as db:
        try:
            # 1. Load Profile
            profile = await profile_repo.get_profile_by_account_id(db, account_id)
            if not profile:
                raise ValueError(f"Company profile not found for account {account_id}")

            # 2. Load Persona
            persona = await persona_loader.load_persona(
                persona_id
            )  # Use o loader refatorado
            if not persona:
                raise ValueError(
                    f"Persona definition '{persona_id}' not found or invalid"
                )

            # 3. Create Initial Simulation Record (usando repo)
            simulation = await simulation_repo.create_simulation(
                db=db, profile_id=profile.id, persona_def=persona
            )
            event_type = SimulationEventTypeEnum.SIMULATION_START
            await simulation_event_repo.create_event(db, simulation.id, event_type)
            events_occurred.append(event_type)

            # --- Initialize Persona State ---
            current_persona_state = PersonaState()  # Começa vazio
            # --------------------------------

            turn = 1
            event_type = SimulationEventTypeEnum.TURN_START
            await simulation_event_repo.create_event(
                db, simulation.id, event_type, turn=turn
            )
            events_occurred.append(event_type)

            # 4. Prepare and Send Initial Message
            initial_payload = webhook_utils.create_message_payload(
                persona.initial_message
            )
            webhook_response = await webhook_utils.send_message_to_webhook(
                initial_payload
            )
            if webhook_response is None:
                raise Exception("Failed to send initial message to webhook.")

            # --- Extract conversation_id ---
            conversation_id_str = webhook_response.get(
                "conversation_id"
            )  # Ajuste a chave se necessário
            if not conversation_id_str:
                raise Exception(
                    "Could not determine conversation_id from webhook response."
                )
            conversation_id = UUID(conversation_id_str)
            logger.info(f"Obtained conversation_id: {conversation_id}")
            # --------------------------------

            await simulation_message_repo.create_message(
                db,
                simulation.id,
                turn=turn,
                role=SimulationMessageRoleEnum.USER,
                content=persona.initial_message,
            )
            event_type = SimulationEventTypeEnum.USER_MESSAGE_SENT
            await simulation_event_repo.create_event(
                db,
                simulation.id,
                event_type,
                turn=turn,
                details={"content": persona.initial_message},
            )
            events_occurred.append(event_type)
            last_message_time = datetime.now(timezone.utc)

            # --- Conversation Loop ---
            while turn < MAX_CONVERSATION_TURNS:
                # 6. Wait for AI Response
                # TODO: Mover poll_for_ai_response para um utilitário ou repo?
                ai_db_message = await webhook_utils.poll_for_ai_response(
                    db, conversation_id, last_message_time
                )
                if ai_db_message is None:
                    final_outcome = SimulationOutcomeEnum.TIMEOUT
                    error_msg = "Timeout waiting for AI response."
                    event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    await simulation_event_repo.create_event(
                        db,
                        simulation.id,
                        event_type,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(event_type)
                    break

                ai_response_text = ai_db_message.content or ""
                last_message_time = ai_db_message.created_at

                # 7. Log AI Response
                await simulation_message_repo.create_message(
                    db,
                    simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.ASSISTANT,
                    content=ai_response_text,
                )
                event_type = SimulationEventTypeEnum.AI_RESPONSE_RECEIVED
                await simulation_event_repo.create_event(
                    db,
                    simulation.id,
                    event_type,
                    turn=turn,
                    details={"content": ai_response_text},
                )
                events_occurred.append(event_type)

                # 8. Check for AI Fallback Event
                if (
                    profile.fallback_contact_info
                    and profile.fallback_contact_info in ai_response_text
                ):
                    event_type = SimulationEventTypeEnum.AI_FALLBACK_DETECTED
                    await simulation_event_repo.create_event(
                        db, simulation.id, event_type, turn=turn
                    )
                    events_occurred.append(event_type)
                    # A checagem de falha baseada neste evento ocorrerá abaixo

                # --- MODIFIED: Use Persona Logic with LLM Extractor ---
                # 9. Get Persona's Next Action (updates state internally)
                next_persona_message, updated_state, terminate, outcome = (
                    await persona_logic.get_next_persona_action(
                        persona=persona,
                        ai_response_text=ai_response_text,
                        current_state=current_persona_state,  # Passa o estado atual
                    )
                )
                current_persona_state = (
                    updated_state  # Atualiza o estado para o próximo turno
                )
                # ----------------------------------------------------

                # 10. Check Termination Conditions
                # a) Check if logic function decided to terminate
                if terminate:
                    final_outcome = (
                        outcome or SimulationOutcomeEnum.SIMULATION_ERROR
                    )  # Usa o outcome da função ou erro
                    logger.info(
                        f"Termination condition met by persona logic. Outcome: {final_outcome.value}"
                    )
                    # Log event (PERSONA_OBJECTIVE_MET ou PERSONA_GAVE_UP já deve ter sido logado pela lógica se necessário)
                    break

                # b) Check explicit failure criteria (turn count, events)
                #    (A lógica de 'state:info_needed_empty' já foi tratada em get_next_persona_action)
                termination_reason = webhook_utils.check_explicit_failure_criteria(
                    persona, turn, events_occurred
                )
                if termination_reason:
                    final_outcome = termination_reason
                    error_msg = f"Failure criterion met: {termination_reason.value}"
                    # Log event (e.g., PERSONA_GAVE_UP or TURN_LIMIT_REACHED)
                    event_type = (
                        SimulationEventTypeEnum.PERSONA_GAVE_UP
                    )  # Ou mapear melhor
                    await simulation_event_repo.create_event(
                        db,
                        simulation.id,
                        event_type,
                        turn=turn,
                        details={"reason": str(final_outcome)},
                    )
                    events_occurred.append(event_type)
                    logger.warning(
                        f"Termination condition met by failure criteria. Outcome: {final_outcome.value}"
                    )
                    break
                # --- END Check Termination Conditions ---

                # --- If conversation continues ---
                if next_persona_message is None:
                    # Should not happen if terminate is False, but safety check
                    logger.error(
                        "Persona logic returned continue but no message. Forcing termination."
                    )
                    final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
                    error_msg = "Persona logic failed to provide next message."
                    event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    await simulation_event_repo.create_event(
                        db,
                        simulation.id,
                        event_type,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(event_type)
                    break

                turn += 1
                event_type = SimulationEventTypeEnum.TURN_START
                await simulation_event_repo.create_event(
                    db, simulation.id, event_type, turn=turn
                )
                events_occurred.append(event_type)

                # 11. Log and Send Persona Response
                await simulation_message_repo.create_message(
                    db,
                    simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.USER,
                    content=next_persona_message,
                )
                event_type = SimulationEventTypeEnum.USER_MESSAGE_SENT
                await simulation_event_repo.create_event(
                    db,
                    simulation.id,
                    event_type,
                    turn=turn,
                    details={"content": next_persona_message},
                )
                events_occurred.append(event_type)

                next_payload = webhook_utils.create_message_payload(
                    next_persona_message
                )
                webhook_response = await webhook_utils.send_message_to_webhook(
                    next_payload
                )
                if webhook_response is None:
                    final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
                    error_msg = "Webhook send failed during conversation."
                    event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    await simulation_event_repo.create_event(
                        db,
                        simulation.id,
                        event_type,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(event_type)
                    break

            # --- End of Loop ---
            # Handle max turns reached if loop finished normally
            if (
                turn >= MAX_CONVERSATION_TURNS
                and simulation.status == SimulationStatusEnum.RUNNING
            ):
                final_outcome = SimulationOutcomeEnum.TURN_LIMIT_REACHED
                error_msg = f"Reached max turn limit ({MAX_CONVERSATION_TURNS})."
                event_type = (
                    SimulationEventTypeEnum.TURN_LIMIT_WARNING
                )  # Ou SIMULATION_END?
                await simulation_event_repo.create_event(
                    db, simulation.id, event_type, turn=turn
                )
                events_occurred.append(event_type)

            # Determine final status
            if (
                final_outcome != SimulationOutcomeEnum.SIMULATION_ERROR
                and final_outcome != SimulationOutcomeEnum.TIMEOUT
                and final_outcome != SimulationOutcomeEnum.AI_ERROR
            ):  # Consider other potential error outcomes
                final_status = SimulationStatusEnum.COMPLETED
            else:
                final_status = SimulationStatusEnum.FAILED  # Ou TIMEOUT

        except Exception as e:
            logger.exception(f"Exception during simulation run: {e}")
            final_status = SimulationStatusEnum.FAILED
            # Garante que final_outcome reflita o erro se não foi setado antes
            if (
                final_outcome == SimulationOutcomeEnum.SIMULATION_ERROR
                and error_msg == "Simulation did not complete loop."
            ):
                final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
            error_msg = str(e)
            if simulation:  # Log event if simulation record exists
                event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                await simulation_event_repo.create_event(
                    db,
                    simulation.id,
                    event_type,
                    turn=turn,
                    details={"error": error_msg},
                )
                events_occurred.append(event_type)

        finally:
            # --- Update Final Simulation Record ---
            if simulation:
                end_time = time.time()
                duration = int(end_time - start_time)
                # Use repo para atualizar
                update_data = {
                    "status": final_status,
                    "outcome": final_outcome,
                    "error_message": (
                        error_msg
                        if final_status != SimulationStatusEnum.COMPLETED
                        else None
                    ),
                    "turn_count": turn,
                    "simulation_duration_seconds": duration,
                    "fallback_used": SimulationEventTypeEnum.AI_FALLBACK_DETECTED
                    in events_occurred,
                    # evaluation_metrics pode ser atualizado depois por outro processo
                }
                await simulation_repo.update_simulation(
                    db, db_simulation=simulation, update_data=update_data
                )

                event_type = SimulationEventTypeEnum.SIMULATION_END
                await simulation_event_repo.create_event(
                    db,
                    simulation.id,
                    event_type,
                    turn=turn,
                    details={"final_outcome": str(final_outcome)},
                )
                await db.commit()  # Commit final
                logger.info(
                    f"Simulation {simulation.id} finished with Status: {final_status}, Outcome: {final_outcome}, Duration: {duration}s"
                )
            else:
                logger.error("Simulation failed before record could be created.")

    logger.info(
        f"--- Simulation Finished for Account: {account_id}, Persona: {persona_id} ---"
    )
