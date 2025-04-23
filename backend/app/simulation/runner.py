# backend/app/simulation/runner.py

import asyncio
import time
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

# Removido: from sqlalchemy import select (não precisamos mais aqui se repos fazem tudo)

# App Imports
from app.database import AsyncSessionLocal

# Modelos e Enums
from app.models.simulation.simulation import (
    Simulation,
    SimulationStatusEnum,
    SimulationOutcomeEnum,
)
from app.models.simulation.simulation_message import SimulationMessageRoleEnum
from app.models.simulation.simulation_event import SimulationEventTypeEnum

# Schemas
from app.simulation.schemas.persona_definition import PersonaDefinition
from app.simulation.schemas.persona_state import PersonaState  # Importar PersonaState

# Repos
from app.services.repository import company_profile as profile_repo

# Usar repos de simulação
from app.simulation.repositories import (
    simulation as simulation_repo,
    simulation_message as simulation_message_repo,
    simulation_event as simulation_event_repo,
)

# Persona Logic & Loader
from app.simulation.personas import loader as persona_loader
from app.simulation.personas import logic as persona_logic

# Config
from app.simulation.config import (
    SIMULATION_ACCOUNT_ID,
    SIMULATION_INBOX_ID,
    POLL_INTERVAL_SECONDS,
    MAX_POLL_ATTEMPTS,
    MAX_CONVERSATION_TURNS,
)

# Utils
from app.simulation.utils import webhook as webhook_utils
from app.simulation.utils.cleanup import reset_simulation_conversation

# --- Main Simulation Logic ---


async def run_single_simulation(persona_id: str, reset_conversation: bool = False):
    """
    Orchestrates and runs a single simulation instance.
    Optionally resets the conversation history before starting.
    """

    account_id = SIMULATION_ACCOUNT_ID
    inbox_id = SIMULATION_INBOX_ID

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
    conversation_id: Optional[UUID] = None

    async with AsyncSessionLocal() as db:
        try:
            # 1. Load Profile
            profile = await profile_repo.get_profile_by_account_id(db, account_id)
            if not profile:
                raise ValueError(f"Company profile not found for account {account_id}")

            # 2. Load Persona
            persona = await persona_loader.load_persona(persona_id)
            if not persona:
                raise ValueError(
                    f"Persona definition '{persona_id}' not found or invalid"
                )

            if reset_conversation:
                await reset_simulation_conversation(
                    db=db,
                    account_id=account_id,
                    inbox_id=inbox_id,
                    contact_identifier=persona.simulation_contact_identifier,  # Pega da persona carregada
                )
                await db.commit()
                logger.info("Reset transaction committed.")
            else:
                logger.error(
                    f"Simulation Inbox {SIMULATION_INBOX_ID} not found. Cannot reset conversation."
                )
                # Decide se continua ou aborta se o inbox não for encontrado
                raise ValueError(f"Simulation Inbox {SIMULATION_INBOX_ID} not found.")

            # 3. Create Initial Simulation Record
            simulation = await simulation_repo.create_simulation(
                db, profile_id=profile.id, persona_def=persona
            )
            event_type = SimulationEventTypeEnum.SIMULATION_START
            await simulation_event_repo.create_event(
                db, simulation_id=simulation.id, event_type=event_type
            )
            events_occurred.append(event_type)

            # --- Initialize Persona State ---
            current_persona_state = PersonaState()  # Começa vazio
            # --------------------------------

            turn = 1
            event_type = SimulationEventTypeEnum.TURN_START
            await simulation_event_repo.create_event(
                db, simulation_id=simulation.id, event_type=event_type, turn=turn
            )
            events_occurred.append(event_type)

            # 4. Prepare and Send Initial Message
            initial_payload = webhook_utils.create_message_payload(
                message_text=persona.initial_message,
                identifier=persona.simulation_contact_identifier,
            )
            webhook_response = await webhook_utils.send_message_to_webhook(
                initial_payload
            )
            if webhook_response is None:
                raise Exception("Failed to send initial message to webhook.")

            # Extract conversation_id
            conversation_id_str = webhook_response.get(
                "conversation_id"
            )  # Ajuste a chave se necessário
            if not conversation_id_str:
                raise Exception(
                    "Could not determine conversation_id from webhook response."
                )
            conversation_id = UUID(conversation_id_str)
            logger.info(f"Obtained conversation_id: {conversation_id}")

            await simulation_message_repo.create_message(
                db,
                simulation_id=simulation.id,
                turn=turn,
                role=SimulationMessageRoleEnum.USER,
                content=persona.initial_message,
            )
            event_type = SimulationEventTypeEnum.USER_MESSAGE_SENT
            await simulation_event_repo.create_event(
                db,
                simulation_id=simulation.id,
                event_type=event_type,
                turn=turn,
                details={"content": persona.initial_message},
            )
            events_occurred.append(event_type)
            last_message_time = datetime.now(timezone.utc)

            # --- Conversation Loop ---
            while turn < MAX_CONVERSATION_TURNS:
                # 6. Wait for AI Response
                ai_db_message = await webhook_utils.poll_for_ai_response(
                    db, conversation_id, last_message_time
                )
                if ai_db_message is None:
                    final_outcome = SimulationOutcomeEnum.TIMEOUT
                    error_msg = "Timeout waiting for AI response."
                    event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=event_type,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(event_type)
                    break  # Sai do loop por timeout

                ai_response_text = ai_db_message.content or ""
                last_message_time = ai_db_message.created_at

                # 7. Log AI Response
                await simulation_message_repo.create_message(
                    db,
                    simulation_id=simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.ASSISTANT,
                    content=ai_response_text,
                )
                event_type = SimulationEventTypeEnum.AI_RESPONSE_RECEIVED
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=event_type,
                    turn=turn,
                    details={"content": ai_response_text},
                )
                events_occurred.append(event_type)

                # 8. Check for AI Fallback Event (apenas loga, a checagem de critério vem depois)
                if (
                    profile.fallback_contact_info
                    and profile.fallback_contact_info in ai_response_text
                ):
                    event_type = SimulationEventTypeEnum.AI_FALLBACK_DETECTED
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=event_type,
                        turn=turn,
                    )
                    events_occurred.append(event_type)

                # --- MODIFIED: Use New Persona Logic ---
                # 9. Get Persona's Next Action (updates state internally)
                next_persona_message, updated_state, terminate_logic, outcome_logic = (
                    await persona_logic.get_next_persona_action(
                        persona=persona,
                        ai_response_text=ai_response_text,
                        current_state=current_persona_state,  # Passa o estado atual
                    )
                )
                current_persona_state = (
                    updated_state  # Atualiza o estado para o próximo turno
                )
                # --------------------------------------

                # 10. Check Termination Conditions
                # a) Check if logic function decided to terminate
                if terminate_logic:
                    final_outcome = (
                        outcome_logic or SimulationOutcomeEnum.SIMULATION_ERROR
                    )  # Usa o outcome da função
                    logger.info(
                        f"Termination condition met by persona logic. Outcome: {final_outcome.value}"
                    )
                    # Log event (PERSONA_OBJECTIVE_MET já deve ter sido logado pela lógica se necessário)
                    # Se for um outcome de sucesso, logamos aqui
                    if final_outcome in [
                        SimulationOutcomeEnum.SALE_COMPLETED,
                        SimulationOutcomeEnum.LEAD_QUALIFIED,
                        SimulationOutcomeEnum.INFO_OBTAINED,
                    ]:
                        event_type = SimulationEventTypeEnum.PERSONA_OBJECTIVE_MET
                        await simulation_event_repo.create_event(
                            db,
                            simulation_id=simulation.id,
                            event_type=event_type,
                            turn=turn,
                            details={"outcome": str(final_outcome)},
                        )
                        events_occurred.append(event_type)
                    break  # Sai do loop

                # b) Check explicit failure criteria (turn count, events)
                #    (A lógica de 'state:info_needed_empty' já foi tratada em get_next_persona_action)
                #    Usamos a função que movemos para utils
                termination_reason = webhook_utils.check_explicit_failure_criteria(
                    persona, turn, events_occurred
                )
                if termination_reason:
                    final_outcome = termination_reason
                    error_msg = f"Failure criterion met: {termination_reason.value}"
                    event_type = (
                        SimulationEventTypeEnum.PERSONA_GAVE_UP
                    )  # Ou mapear melhor
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=event_type,
                        turn=turn,
                        details={"reason": str(final_outcome)},
                    )
                    events_occurred.append(event_type)
                    logger.warning(
                        f"Termination condition met by failure criteria. Outcome: {final_outcome.value}"
                    )
                    break  # Sai do loop
                # --- END Check Termination Conditions ---

                # --- If conversation continues ---
                if next_persona_message is None:
                    # Segurança: Se a lógica não terminou mas não deu próxima msg
                    logger.error(
                        "Persona logic returned continue but no message. Forcing termination."
                    )
                    final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
                    error_msg = "Persona logic failed to provide next message."
                    event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=event_type,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(event_type)
                    break

                turn += 1
                event_type = SimulationEventTypeEnum.TURN_START
                await simulation_event_repo.create_event(
                    db, simulation_id=simulation.id, event_type=event_type, turn=turn
                )
                events_occurred.append(event_type)

                # 11. Log and Send Persona Response
                await simulation_message_repo.create_message(
                    db,
                    simulation_id=simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.USER,
                    content=next_persona_message,
                )
                event_type = SimulationEventTypeEnum.USER_MESSAGE_SENT
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=event_type,
                    turn=turn,
                    details={"content": next_persona_message},
                )
                events_occurred.append(event_type)

                next_payload = webhook_utils.create_message_payload(
                    message_text=next_persona_message,
                    identifier=persona.simulation_contact_identifier,
                    conversation_id=conversation_id,
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
                        simulation_id=simulation.id,
                        event_type=event_type,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(event_type)
                    break

            # --- End of Loop ---
            if (
                turn >= MAX_CONVERSATION_TURNS
                and simulation.status == SimulationStatusEnum.RUNNING
            ):
                final_outcome = SimulationOutcomeEnum.TURN_LIMIT_REACHED
                error_msg = f"Reached max turn limit ({MAX_CONVERSATION_TURNS})."
                event_type = SimulationEventTypeEnum.TURN_LIMIT_WARNING
                await simulation_event_repo.create_event(
                    db, simulation_id=simulation.id, event_type=event_type, turn=turn
                )
                events_occurred.append(event_type)

            # Determine final status based on the final_outcome
            success_outcomes = [
                SimulationOutcomeEnum.SALE_COMPLETED,
                SimulationOutcomeEnum.LEAD_QUALIFIED,
                SimulationOutcomeEnum.INFO_OBTAINED,
            ]
            if final_outcome in success_outcomes:
                final_status = SimulationStatusEnum.COMPLETED
                error_msg = None  # Clear error message on success
            else:
                final_status = SimulationStatusEnum.FAILED
                # Keep error_msg if already set, otherwise use outcome
                if error_msg == "Simulation did not complete loop.":
                    error_msg = f"Simulation ended with non-success outcome: {final_outcome.value}"

        except Exception as e:
            logger.exception(f"Exception during simulation run: {e}")
            final_status = SimulationStatusEnum.FAILED
            # Ensure outcome reflects the error if not already set
            if (
                final_outcome == SimulationOutcomeEnum.SIMULATION_ERROR
                and error_msg == "Simulation did not complete loop."
            ):
                final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
            error_msg = str(e)
            if simulation:  # Log event if simulation record exists
                event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                # Use repo to log event
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=event_type,
                    turn=turn,
                    details={"error": error_msg},
                )
                # No need to append to events_occurred here as we are exiting

        finally:
            # --- Update Final Simulation Record ---
            if simulation:
                end_time = time.time()
                duration = int(end_time - start_time)
                update_data = {
                    "status": final_status,
                    "outcome": final_outcome,
                    "error_message": error_msg,
                    "turn_count": turn,
                    "simulation_duration_seconds": duration,
                    "fallback_used": SimulationEventTypeEnum.AI_FALLBACK_DETECTED
                    in events_occurred,
                }
                try:
                    await simulation_repo.update_simulation(
                        db, db_simulation=simulation, update_data=update_data
                    )
                except Exception as update_err:
                    logger.error(
                        f"Failed to update final simulation record {simulation.id}: {update_err}"
                    )

                event_type = SimulationEventTypeEnum.SIMULATION_END
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=event_type,
                    turn=turn,
                    details={"final_outcome": str(final_outcome)},
                )
                await db.commit()  # Commit final state
                logger.info(
                    f"Simulation {simulation.id} finished with Status: {final_status}, Outcome: {final_outcome}, Duration: {duration}s"
                )
            else:
                logger.error("Simulation failed before record could be created.")

    logger.info(
        f"--- Simulation Finished for Account: {account_id}, Persona: {persona_id} ---"
    )
