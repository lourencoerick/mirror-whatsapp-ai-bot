import time
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from loguru import logger

from app.database import AsyncSessionLocal
from app.models.simulation.simulation import (
    Simulation,
    SimulationStatusEnum,
    SimulationOutcomeEnum,
)
from app.models.simulation.simulation_message import SimulationMessageRoleEnum
from app.models.simulation.simulation_event import SimulationEventTypeEnum
from app.simulation.schemas.persona_definition import PersonaDefinition
from app.simulation.schemas.persona_state import PersonaState
from app.services.repository import company_profile as profile_repo
from app.simulation.repositories import (
    simulation as simulation_repo,
    simulation_message as simulation_message_repo,
    simulation_event as simulation_event_repo,
)
from app.simulation.personas import loader as persona_loader
from app.simulation.personas import logic as persona_logic
from app.simulation.config import (
    SIMULATION_ACCOUNT_ID,
    SIMULATION_INBOX_ID,
    MAX_CONVERSATION_TURNS,
)
from app.simulation.utils import webhook as webhook_utils
from app.simulation.utils.cleanup import reset_simulation_conversation


async def run_single_simulation(persona_id: str, reset_conversation: bool = False):
    """
    Orchestrates and runs a single simulation instance.
    Optionally resets the conversation history before starting.
    """
    account_id = SIMULATION_ACCOUNT_ID
    inbox_id = SIMULATION_INBOX_ID

    logger.info(
        f"--- Starting simulation: account={account_id}, persona={persona_id} ---"
    )
    start_time = time.time()
    simulation: Optional[Simulation] = None
    final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
    final_status = SimulationStatusEnum.FAILED
    error_msg: Optional[str] = "Simulation did not complete loop."
    turn = 0
    events_occurred: List[SimulationEventTypeEnum] = []
    conversation_id: Optional[UUID] = None

    async with AsyncSessionLocal() as db:
        try:
            # Load company profile
            profile = await profile_repo.get_profile_by_account_id(db, account_id)
            if not profile:
                raise ValueError(f"Company profile not found for account {account_id}")

            # Load persona definition
            persona = await persona_loader.load_persona(persona_id)
            if not persona:
                raise ValueError(f"Persona '{persona_id}' not found or invalid")

            # Optionally reset conversation
            if reset_conversation:
                await reset_simulation_conversation(
                    db=db,
                    account_id=account_id,
                    inbox_id=inbox_id,
                    contact_identifier=persona.simulation_contact_identifier,
                )
                await db.commit()
                logger.info("Reset transaction committed.")
            else:
                raise ValueError(
                    f"Inbox {inbox_id} not found. Cannot reset conversation."
                )

            # Create initial simulation record
            simulation = await simulation_repo.create_simulation(
                db, profile_id=profile.id, persona_def=persona
            )
            event_type = SimulationEventTypeEnum.SIMULATION_START
            await simulation_event_repo.create_event(
                db, simulation_id=simulation.id, event_type=event_type
            )
            events_occurred.append(event_type)

            # Initialize persona state
            current_persona_state = PersonaState()

            turn = 1
            event_type = SimulationEventTypeEnum.TURN_START
            await simulation_event_repo.create_event(
                db, simulation_id=simulation.id, event_type=event_type, turn=turn
            )
            events_occurred.append(event_type)

            # Send initial message
            initial_payload = webhook_utils.create_message_payload(
                message_text=persona.initial_message,
                identifier=persona.simulation_contact_identifier,
            )
            webhook_response = await webhook_utils.send_message_to_webhook(
                initial_payload
            )
            if webhook_response is None:
                raise Exception("Failed to send initial message to webhook.")

            conversation_id_str = webhook_response.get("conversation_id")
            if not conversation_id_str:
                raise Exception("No conversation_id in webhook response.")
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

            # Conversation loop
            while turn < MAX_CONVERSATION_TURNS:
                # Wait for AI response
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
                    break

                ai_response_text = ai_db_message.content or ""
                last_message_time = ai_db_message.created_at

                # Log AI response
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

                # Detect fallback trigger
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

                # Compute next persona action
                next_persona_message, updated_state, terminate_logic, outcome_logic = (
                    await persona_logic.get_next_persona_action(
                        persona=persona,
                        ai_response_text=ai_response_text,
                        current_state=current_persona_state,
                    )
                )
                current_persona_state = updated_state

                # Terminate if logic dictates
                if terminate_logic:
                    final_outcome = (
                        outcome_logic or SimulationOutcomeEnum.SIMULATION_ERROR
                    )
                    logger.info(f"Termination by persona logic: {final_outcome.value}")
                    if final_outcome in {
                        SimulationOutcomeEnum.SALE_COMPLETED,
                        SimulationOutcomeEnum.LEAD_QUALIFIED,
                        SimulationOutcomeEnum.INFO_OBTAINED,
                    }:
                        event_type = SimulationEventTypeEnum.PERSONA_OBJECTIVE_MET
                        await simulation_event_repo.create_event(
                            db,
                            simulation_id=simulation.id,
                            event_type=event_type,
                            turn=turn,
                            details={"outcome": str(final_outcome)},
                        )
                        events_occurred.append(event_type)
                    break

                # Check failure criteria
                termination_reason = webhook_utils.check_explicit_failure_criteria(
                    persona, turn, events_occurred
                )
                if termination_reason:
                    final_outcome = termination_reason
                    error_msg = f"Failure criterion met: {termination_reason.value}"
                    event_type = SimulationEventTypeEnum.PERSONA_GAVE_UP
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=event_type,
                        turn=turn,
                        details={"reason": str(final_outcome)},
                    )
                    events_occurred.append(event_type)
                    logger.warning(f"Failure criterion met: {final_outcome.value}")
                    break

                # Ensure next message exists
                if next_persona_message is None:
                    final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
                    error_msg = "No next message from persona logic."
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

                # Send persona response
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

            # Handle turn limit
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

            # Determine final status
            if final_outcome in {
                SimulationOutcomeEnum.SALE_COMPLETED,
                SimulationOutcomeEnum.LEAD_QUALIFIED,
                SimulationOutcomeEnum.INFO_OBTAINED,
            }:
                final_status = SimulationStatusEnum.COMPLETED
                error_msg = None
            else:
                final_status = SimulationStatusEnum.FAILED
                if error_msg == "Simulation did not complete loop.":
                    error_msg = f"Ended with non-success outcome: {final_outcome.value}"

        except Exception as e:
            logger.exception(f"Exception during simulation run: {e}")
            final_status = SimulationStatusEnum.FAILED
            final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
            error_msg = str(e)
            if simulation:
                event_type = SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=event_type,
                    turn=turn,
                    details={"error": error_msg},
                )

        finally:
            # Update simulation record and commit
            if simulation:
                duration = int(time.time() - start_time)
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
                        f"Failed to update simulation {simulation.id}: {update_err}"
                    )

                event_type = SimulationEventTypeEnum.SIMULATION_END
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=event_type,
                    turn=turn,
                    details={"final_outcome": str(final_outcome)},
                )
                await db.commit()
                logger.info(
                    f"Simulation {simulation.id} finished: status={final_status}, outcome={final_outcome}, duration={duration}s"
                )
            else:
                logger.error("Simulation failed before record creation.")

    logger.info(
        f"--- Simulation finished: account={account_id}, persona={persona_id} ---"
    )
