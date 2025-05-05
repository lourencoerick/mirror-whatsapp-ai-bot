# backend/app/simulation/runner.py

import time
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from loguru import logger

# Database and Models
from app.database import AsyncSessionLocal
from app.models.simulation.simulation import (
    Simulation,
    SimulationStatusEnum,
    SimulationOutcomeEnum,
)
from app.models.simulation.simulation_message import SimulationMessageRoleEnum
from app.models.simulation.simulation_event import SimulationEventTypeEnum
from app.models.account import Account
from app.models.message import Message  # Needed for type hint if loading full history

# Schemas
from app.simulation.schemas.persona import PersonaRead
from app.simulation.schemas.persona_state import PersonaState  # Schema simplificado
from app.api.schemas.simulation import (
    SimulationMessageCreate,
    SimulationMessageEnqueueResponse,
)

# Repositories and Services
from app.services.repository import company_profile as profile_repo
from app.services.repository import contact as contact_repo
from app.simulation.repositories import (
    simulation as simulation_repo,
    simulation_message as simulation_message_repo,
    simulation_event as simulation_event_repo,
)

# Persona Modules
from app.simulation.personas import loader as persona_loader

# Importar a função refatorada de logic.py
from app.simulation.personas.logic import get_next_persona_action

# Config and Utils
from app.simulation.config import MAX_CONVERSATION_TURNS
from app.simulation.utils import webhook as webhook_utils
from app.simulation.utils.cleanup import reset_simulation_conversation
from app.api.routes.simulation import _enqueue_simulation_message


async def run_single_simulation(
    account: Account,  # Passar o objeto Account diretamente é mais seguro
    persona_id_str: str,
    reset_conversation: bool = False,
):
    """
    Orchestrates and runs a single simulation instance using an LLM-driven persona.
    Optionally resets the conversation history before starting.

    Args:
        account: The Account object for which the simulation runs.
        persona_id_str: The identifier string of the persona to use.
        reset_conversation: If True, clears previous messages for the contact.
    """
    account_id = account.id
    inbox_id = (
        account.simulation_inbox_id
    )  # Assume simulation_inbox_id está no objeto Account

    if not inbox_id:
        logger.error(
            f"Account {account_id} does not have a simulation_inbox_id configured."
        )
        # Poderia retornar um status de erro ou levantar uma exceção
        return  # Ou raise ValueError(...)

    logger.info(
        f"--- Starting simulation (LLM Persona): account={account_id}, persona={persona_id_str} ---"
    )
    start_time = time.time()
    simulation: Optional[Simulation] = None
    final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR  # Default outcome
    final_status = SimulationStatusEnum.FAILED  # Default status
    error_msg: Optional[str] = (
        "Simulation did not complete its execution loop properly."  # Default error
    )
    turn = 0
    events_occurred: List[SimulationEventTypeEnum] = []
    conversation_id: Optional[UUID] = None
    # Guarda o histórico simplificado para passar para a persona LLM
    conversation_history_for_persona: List[Dict[str, str]] = []

    async with AsyncSessionLocal() as db:
        try:
            # 1. Load Profile and Persona
            profile = await profile_repo.get_profile_by_account_id(db, account_id)
            if not profile:
                raise ValueError(f"Company profile not found for account {account_id}")

            persona = await persona_loader.load_persona_from_db(db, persona_id_str)
            if not persona:
                raise ValueError(f"Persona '{persona_id_str}' not found or invalid")

            # 2. Find Contact Inbox and Conversation ID
            contact_inbox = await contact_repo.find_contact_inbox_by_contact_and_inbox(
                db=db,
                account_id=account_id,
                contact_id=persona.contact_id,  # ID do contato associado à persona
                inbox_id=inbox_id,
            )
            if not contact_inbox or not contact_inbox.conversation:
                # Isso não deveria acontecer se a persona foi criada corretamente
                raise ValueError(
                    f"Contact inbox or conversation not found for persona {persona_id_str} / contact {persona.contact_id}"
                )
            conversation_id = contact_inbox.conversation.id
            logger.info(f"Using Conversation ID: {conversation_id}")

            # 3. Optionally Reset Conversation
            if reset_conversation:
                logger.warning(
                    f"Resetting conversation {conversation_id} for simulation..."
                )
                await reset_simulation_conversation(
                    db=db,
                    account_id=account_id,
                    inbox_id=inbox_id,
                    contact_identifier=persona.simulation_contact_identifier,  # Usa o identificador da persona
                )
                await db.commit()  # Commit reset before starting simulation record
                logger.info("Conversation reset committed.")
                # Limpa histórico local também
                conversation_history_for_persona = []

            # 4. Create Initial Simulation Record
            simulation = await simulation_repo.create_simulation(
                db, profile_id=profile.id, persona_id=persona.id
            )
            await simulation_event_repo.create_event(
                db,
                simulation_id=simulation.id,
                event_type=SimulationEventTypeEnum.SIMULATION_START,
            )
            events_occurred.append(SimulationEventTypeEnum.SIMULATION_START)
            await db.commit()  # Commit simulation creation

            # 5. Initialize Persona State (Simplificado)
            current_persona_state = PersonaState(turn_count=0)

            # 6. Start Turn 1
            turn = 1
            await simulation_event_repo.create_event(
                db,
                simulation_id=simulation.id,
                event_type=SimulationEventTypeEnum.TURN_START,
                turn=turn,
            )
            events_occurred.append(SimulationEventTypeEnum.TURN_START)

            # 7. Send Initial Persona Message
            initial_msg_content = persona.initial_message
            message_payload = SimulationMessageCreate(content=initial_msg_content)
            # Envia via webhook (simulando entrada do usuário)
            await _enqueue_simulation_message(
                db=db,
                account_id=account_id,
                conversation_id=conversation_id,
                message_payload=message_payload,
            )
            last_message_time = datetime.now(
                timezone.utc
            )  # Marca o tempo *após* enviar

            # Loga a mensagem no DB da simulação
            await simulation_message_repo.create_message(
                db,
                simulation_id=simulation.id,
                turn=turn,
                role=SimulationMessageRoleEnum.USER,
                content=initial_msg_content,
            )
            await simulation_event_repo.create_event(
                db,
                simulation_id=simulation.id,
                event_type=SimulationEventTypeEnum.USER_MESSAGE_SENT,
                turn=turn,
                details={"content": initial_msg_content},
            )
            events_occurred.append(SimulationEventTypeEnum.USER_MESSAGE_SENT)
            # Adiciona ao histórico local para o Persona LLM
            conversation_history_for_persona.append(
                {"role": "user", "content": initial_msg_content}
            )
            await db.commit()  # Commit após o primeiro turno do usuário

            # 8. Conversation Loop
            while turn < MAX_CONVERSATION_TURNS:
                logger.info(
                    f"--- Simulation Turn {turn} (Persona: {persona_id_str}) ---"
                )

                # 8.1 Wait for AI response
                logger.debug(f"Polling for AI response after {last_message_time}...")
                ai_db_message = await webhook_utils.poll_for_ai_response(
                    db, conversation_id, last_message_time
                )
                if ai_db_message is None:
                    final_outcome = SimulationOutcomeEnum.TIMEOUT
                    error_msg = f"Timeout waiting for AI response on turn {turn}."
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(
                        SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    )
                    logger.error(error_msg)
                    break  # Sai do loop while

                ai_response_text = ai_db_message.content or ""
                last_message_time = (
                    ai_db_message.created_at
                )  # Atualiza o tempo da última mensagem recebida
                logger.info(f"AI Response received: '{ai_response_text[:100]}...'")

                # 8.2 Log AI response
                await simulation_message_repo.create_message(
                    db,
                    simulation_id=simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.ASSISTANT,
                    content=ai_response_text,
                )
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=SimulationEventTypeEnum.AI_RESPONSE_RECEIVED,
                    turn=turn,
                    details={"content": ai_response_text},
                )
                events_occurred.append(SimulationEventTypeEnum.AI_RESPONSE_RECEIVED)
                # Adiciona ao histórico local para o Persona LLM
                conversation_history_for_persona.append(
                    {"role": "assistant", "content": ai_response_text}
                )

                # 8.3 Detect fallback trigger (mantido)
                if (
                    profile.fallback_contact_info
                    and profile.fallback_contact_info in ai_response_text
                ):
                    logger.warning("AI fallback detected in response.")
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=SimulationEventTypeEnum.AI_FALLBACK_DETECTED,
                        turn=turn,
                    )
                    events_occurred.append(SimulationEventTypeEnum.AI_FALLBACK_DETECTED)
                    # Considerar se isso deve ser um critério de falha automático

                # 8.4 Compute next persona action using LLM
                logger.debug("Getting next persona action from LLM...")
                next_persona_message, updated_state, terminate_logic, outcome_logic = (
                    await get_next_persona_action(  # Chama a nova função
                        persona=persona,
                        ai_response_text=ai_response_text,
                        current_state=current_persona_state,
                        conversation_history=conversation_history_for_persona,  # Passa o histórico
                    )
                )
                current_persona_state = (
                    updated_state  # Atualiza estado (ex: turn_count)
                )

                # 8.5 Handle Persona Logic Failure
                if (
                    terminate_logic
                    and outcome_logic == SimulationOutcomeEnum.SIMULATION_ERROR
                ):
                    final_outcome = outcome_logic
                    error_msg = (
                        "Persona logic failed to generate response (LLM Error?)."
                    )
                    logger.error(error_msg)
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR,
                        turn=turn,
                        details={"error": error_msg},
                    )
                    events_occurred.append(
                        SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR
                    )
                    break  # Sai do loop while

                # 8.6 Check Explicit Failure Criteria (Turn Count, Fallback etc.)
                termination_reason = webhook_utils.check_explicit_failure_criteria(
                    persona, turn + 1, events_occurred
                )  # Checa para o *próximo* turno
                if termination_reason:
                    final_outcome = termination_reason
                    error_msg = f"Failure criterion met: {termination_reason.value}"
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=SimulationEventTypeEnum.PERSONA_GAVE_UP,
                        turn=turn,
                        details={"reason": str(final_outcome)},
                    )
                    events_occurred.append(SimulationEventTypeEnum.PERSONA_GAVE_UP)
                    logger.warning(f"Failure criterion met: {final_outcome.value}")
                    break  # Sai do loop while

                # 8.7 Check if Persona decided to end (LLM returned no message)
                if next_persona_message is None:
                    logger.info(
                        "Persona LLM did not return a message, assuming natural end."
                    )
                    # Definir um outcome específico? Ou deixar UNKNOWN?
                    final_outcome = (
                        SimulationOutcomeEnum.UNKNOWN
                    )  # Ou criar PERSONA_ENDED_CONVO
                    error_msg = "Persona decided to end the conversation (no message generated)."
                    # Não necessariamente um erro, mas um fim.
                    break  # Sai do loop while

                # --- Preparar Próximo Turno ---
                turn += 1
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=SimulationEventTypeEnum.TURN_START,
                    turn=turn,
                )
                events_occurred.append(SimulationEventTypeEnum.TURN_START)

                # 8.8 Enviar resposta da persona
                logger.info(
                    f"Persona Response (Turn {turn}): '{next_persona_message[:100]}...'"
                )
                await simulation_message_repo.create_message(
                    db,
                    simulation_id=simulation.id,
                    turn=turn,
                    role=SimulationMessageRoleEnum.USER,
                    content=next_persona_message,
                )
                await simulation_event_repo.create_event(
                    db,
                    simulation_id=simulation.id,
                    event_type=SimulationEventTypeEnum.USER_MESSAGE_SENT,
                    turn=turn,
                    details={"content": next_persona_message},
                )
                events_occurred.append(SimulationEventTypeEnum.USER_MESSAGE_SENT)
                # Adiciona ao histórico local para o Persona LLM
                conversation_history_for_persona.append(
                    {"role": "user", "content": next_persona_message}
                )

                message_payload = SimulationMessageCreate(content=next_persona_message)
                # Envia via webhook
                await _enqueue_simulation_message(
                    db=db,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    message_payload=message_payload,
                )
                last_message_time = datetime.now(
                    timezone.utc
                )  # Atualiza tempo após enviar

                await db.commit()  # Commit no final de cada turno completo da persona

            # --- Fim do Loop While ---

            # 9. Handle Turn Limit Reached (se saiu do loop por isso)
            if (
                turn >= MAX_CONVERSATION_TURNS
                and final_status != SimulationStatusEnum.COMPLETED
            ):
                if (
                    final_outcome == SimulationOutcomeEnum.SIMULATION_ERROR
                ):  # Mantém erro se já houve um
                    pass
                else:
                    final_outcome = SimulationOutcomeEnum.TURN_LIMIT_REACHED
                    error_msg = f"Reached max turn limit ({MAX_CONVERSATION_TURNS})."
                    logger.warning(error_msg)
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=SimulationEventTypeEnum.TURN_LIMIT_WARNING,
                        turn=turn,
                    )
                    events_occurred.append(SimulationEventTypeEnum.TURN_LIMIT_WARNING)

            # 10. Determinar Status Final (Simplificado)
            # Sucesso é mais difícil de avaliar automaticamente agora.
            # Consideramos sucesso apenas se um outcome explicitamente positivo foi definido (raro agora).
            # Qualquer outro outcome (Timeout, Turn Limit, Error, Unknown, Gave Up) é FAILED.
            if final_outcome in [
                SimulationOutcomeEnum.SALE_COMPLETED,
                SimulationOutcomeEnum.LEAD_QUALIFIED,
                SimulationOutcomeEnum.INFO_OBTAINED,
            ]:  # Manter estes se forem definidos por alguma lógica futura
                final_status = SimulationStatusEnum.COMPLETED
                error_msg = None  # Limpa msg de erro padrão em caso de sucesso
                logger.info(
                    f"Simulation concluded with SUCCESS outcome: {final_outcome.value}"
                )
            else:
                final_status = SimulationStatusEnum.FAILED
                if (
                    not error_msg
                    or error_msg
                    == "Simulation did not complete its execution loop properly."
                ):
                    error_msg = f"Ended with non-success outcome: {final_outcome.value}"
                logger.warning(
                    f"Simulation concluded with FAILED status. Outcome: {final_outcome.value}. Reason: {error_msg}"
                )

        except (
            ValueError
        ) as ve:  # Captura erros de validação (ex: profile/persona not found)
            logger.error(f"Configuration error during simulation setup: {ve}")
            final_status = SimulationStatusEnum.FAILED
            final_outcome = SimulationOutcomeEnum.SETUP_ERROR
            error_msg = f"Setup Error: {ve}"
        except Exception as e:
            logger.exception(f"Unhandled exception during simulation run: {e}")
            final_status = SimulationStatusEnum.FAILED
            final_outcome = SimulationOutcomeEnum.SIMULATION_ERROR
            error_msg = f"Runtime Error: {str(e)}"
            if simulation:  # Tenta logar evento de erro se a simulação foi criada
                try:
                    await simulation_event_repo.create_event(
                        db,
                        simulation_id=simulation.id,
                        event_type=SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR,
                        turn=turn,
                        details={"error": error_msg},
                    )
                except Exception as log_err:
                    logger.error(
                        f"Failed to log final simulation error event: {log_err}"
                    )

        finally:
            # 11. Update Simulation Record and Commit Final State
            if simulation:
                duration = int(time.time() - start_time)
                update_data = {
                    "status": final_status,
                    "outcome": final_outcome,
                    "error_message": error_msg,
                    "turn_count": turn,  # Turno final alcançado
                    "simulation_duration_seconds": duration,
                    "fallback_used": SimulationEventTypeEnum.AI_FALLBACK_DETECTED
                    in events_occurred,
                }
                try:
                    # Garante que a sessão ainda está ativa antes de atualizar
                    if db.is_active:
                        await simulation_repo.update_simulation(
                            db, db_simulation=simulation, update_data=update_data
                        )
                        await simulation_event_repo.create_event(
                            db,
                            simulation_id=simulation.id,
                            event_type=SimulationEventTypeEnum.SIMULATION_END,
                            turn=turn,
                            details={"final_outcome": str(final_outcome)},
                        )
                        await db.commit()  # Commit final
                        logger.info(
                            f"Simulation {simulation.id} final state committed: status={final_status}, outcome={final_outcome}, duration={duration}s"
                        )
                    else:
                        logger.error(
                            f"Database session inactive before final update for simulation {simulation.id}."
                        )

                except Exception as update_err:
                    logger.error(
                        f"Failed to update simulation {simulation.id} or commit final state: {update_err}"
                    )
                    # Tentar rollback pode não ser possível se a sessão já fechou
            else:
                logger.error(
                    "Simulation failed before record creation, cannot update final state."
                )

    logger.info(
        f"--- Simulation finished: account={account_id}, persona={persona_id_str}, conversation_id={conversation_id} ---"
    )
