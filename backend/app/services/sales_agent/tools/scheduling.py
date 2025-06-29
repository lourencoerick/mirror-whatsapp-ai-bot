# app/services/sales_agent/tools/scheduling.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from loguru import logger
from typing_extensions import Annotated
from datetime import date, datetime, timedelta
from uuid import UUID
import pytz  # Biblioteca para lidar com fusos horários (pip install pytz)
from fastapi import HTTPException


from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage

from app.services.sales_agent.agent_state import AgentState
from app.database import AsyncSessionLocal
from app.services.google_calendar.google_calendar_service import GoogleCalendarService
from app.api.schemas.company_profile import OfferingInfo


@tool
async def check_scheduling_status(
    state: Annotated[AgentState, InjectedState],
) -> str:
    """
    Checks if the scheduling feature is enabled for the company.

    Use this as the very first step before attempting any scheduling-related action
    (like finding available slots or creating an appointment). This tool provides a
    simple Yes/No answer. If the answer is 'No', you should inform the user that
    scheduling is not available and do not proceed with other scheduling tools.

    Args:
        state: The current agent state, used to access the company profile.

    Returns:
        A string, either "Yes, scheduling is enabled." or "No, scheduling is currently disabled.".
    """
    tool_name = "check_scheduling_status"
    logger.info(f"--- Executing Tool: {tool_name} ---")

    profile = state.company_profile

    if profile and profile.is_scheduling_enabled:
        logger.info(f"[{tool_name}] Result: Scheduling is ENABLED.")
        return "Yes, scheduling is enabled. Now, check if the offering id allows a appointement scheduling."
    else:
        logger.info(f"[{tool_name}] Result: Scheduling is DISABLED.")
        return "No, scheduling is currently disabled for the company. This means that you have to guide the customer to the checkout link, using the sales principles."


@tool
async def get_available_slots(
    target_date_str: str,
    offering_id_str: str,
    state: Annotated[AgentState, InjectedState],
) -> str:
    """
    Checks for available appointment slots on a specific date for a specific service.

    Use this tool when a user expresses interest in scheduling a service and provides a
    date. You need both the date and the specific service (via its ID) they are
    interested in to calculate the correct slot durations.

    Args:
        target_date_str: The desired date for the appointment, in "YYYY-MM-DD" format.
        offering_id_str: The unique ID of the offering (product/service) that requires
                         scheduling. This is needed to determine the appointment duration.
        state: The current agent state, used to access company profile details like
               scheduling settings, availability rules, and offering details.

    Returns:
        A string containing a list of available time slots in "HH:MM" format,
        or a message indicating that no slots are available for that day.
        If the offering does not require scheduling or if scheduling is not enabled,
        it will return an informative message.
    """
    tool_name = "get_available_slots"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(
        f"[{tool_name}] Received date: '{target_date_str}', Offering ID: '{offering_id_str}'"
    )

    # --- 1. Validações e Extração de Dados do Estado ---
    profile = state.company_profile
    if (
        not profile
        or not profile.is_scheduling_enabled
        or not profile.scheduling_calendar_id
    ):
        logger.warning(
            f"[{tool_name}] Scheduling is not enabled or configured for this profile."
        )
        return "Desculpe, a funcionalidade de agendamento não está ativada para esta empresa no momento."

    try:
        target_date = date.fromisoformat(target_date_str)
        offering_uuid = UUID(offering_id_str)
    except (ValueError, TypeError):
        logger.warning(f"[{tool_name}] Invalid date or UUID format provided.")
        return "Por favor, forneça uma data válida no formato AAAA-MM-DD e um ID de oferta válido."

    today = date.today()
    if target_date < today:
        logger.warning(f"[{tool_name}] User requested a past date: {target_date_str}.")
        return "Não é possível agendar para uma data que já passou. Por favor, escolha hoje ou uma data futura."

    # Encontrar a oferta e sua duração
    target_offering: Optional[OfferingInfo] = next(
        (o for o in profile.offering_overview if o.id == offering_uuid), None
    )

    if (
        not target_offering
        or not target_offering.requires_scheduling
        or not target_offering.duration_minutes
    ):
        logger.warning(
            f"[{tool_name}] Offering {offering_id_str} does not require scheduling or has no duration."
        )
        return "A oferta selecionada não parece necessitar de um agendamento ou não tem uma duração definida."

    # --- 2. Executar o Serviço ---
    try:
        calendar_service = GoogleCalendarService()
        async with AsyncSessionLocal() as db:
            available_slots = await calendar_service.get_available_slots(
                db=db,
                user_id=profile.scheduling_user_id,
                calendar_id=profile.scheduling_calendar_id,
                target_date=target_date,
                duration_minutes=target_offering.duration_minutes,
                availability_rules=profile.availability_rules or [],
                min_notice_hours=profile.scheduling_min_notice_hours,
            )

        if not available_slots:
            logger.info(
                f"[{tool_name}] No available slots found for {target_date_str}."
            )
            return f"Não encontrei horários disponíveis para o dia {target_date_str}. Gostaria de tentar outra data?"

        # --- 3. Formatar a Saída para a IA ---
        formatted_slots = ", ".join(available_slots)
        logger.info(f"[{tool_name}] Found slots: {formatted_slots}")
        return f"Os seguintes horários estão disponíveis em {target_date_str}: {formatted_slots}."

    except Exception as e:
        logger.exception(f"[{tool_name}] Error getting available slots: {e}")
        return "Ocorreu um erro ao tentar verificar os horários disponíveis. Por favor, tente novamente mais tarde."


@tool
async def create_appointment(
    # Os argumentos agora são desempacotados do schema
    appointment_datetime_str: str,
    offering_id_str: str,
    customer_email: str,
    customer_name: str,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    customer_notes: Optional[str] = None,
) -> str:
    """
    Creates a new appointment (event) in the company's Google Calendar and invites the customer.

    Use this tool ONLY after you have confirmed:
    1. The exact date and time slot with the user.
    2. The specific service they want.
    3. The user's email address to send the calendar invitation.
    4. The user's full name to improve the quality of the invitation.
    If you don't have the user's email or user's name, you MUST ask for it before calling this tool.

    IMPORTANT: You MUST have the customer's real email address before calling this tool.
    If you do not have the email, you MUST ask the user for it first.
    DO NOT invent or guess an email address. If the user refuses to provide an
    email, explain that you cannot complete the booking without it.
    """
    tool_name = "create_appointment"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(
        f"[{tool_name}] Args: dt='{appointment_datetime_str}', offer='{offering_id_str}', customer='{customer_name}'"
    )

    tool_name = "create_appointment"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(
        f"[{tool_name}] Received datetime: '{appointment_datetime_str}', Offering ID: '{offering_id_str}'"
    )

    # --- 1. Validações e Extração de Dados ---
    customer_phone = state.customer_phone
    profile = state.company_profile
    if (
        not profile
        or not profile.is_scheduling_enabled
        or not profile.scheduling_user_id
        or not profile.scheduling_calendar_id
    ):
        logger.warning(f"[{tool_name}] Scheduling is not enabled or fully configured.")
        tool_messsage = "Desculpe, a funcionalidade de agendamento não está configurada para criar o evento."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                ]
            }
        )

    try:
        # Converte a string de data/hora para um objeto datetime "naive" (sem fuso horário)
        naive_start_time = datetime.strptime(appointment_datetime_str, "%Y-%m-%d %H:%M")
        offering_uuid = UUID(offering_id_str)
    except (ValueError, TypeError):
        logger.warning(f"[{tool_name}] Invalid datetime or UUID format provided.")
        tool_messsage = "Por favor, forneça uma data e hora válidas (AAAA-MM-DD HH:MM) e um ID de oferta válido."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                ]
            }
        )

    # Encontrar a oferta e sua duração
    target_offering: Optional[OfferingInfo] = next(
        (o for o in profile.offering_overview if o.id == offering_uuid), None
    )

    # 1. A oferta existe?
    if not target_offering:
        logger.warning(f"[{tool_name}] Offering with ID {offering_id_str} not found.")
        tool_messsage = "Não consegui encontrar a oferta com o ID fornecido."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                ]
            }
        )

    # 2. A oferta requer agendamento?
    if not target_offering.requires_scheduling:
        logger.warning(
            f"[{tool_name}] Offering '{target_offering.name}' does not require scheduling."
        )
        tool_messsage = f"A oferta '{target_offering.name}' não precisa de agendamento."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                ]
            }
        )

    # 3. A oferta tem uma duração definida?
    if not target_offering.duration_minutes:
        logger.warning(
            f"[{tool_name}] Offering '{target_offering.name}' has no duration set."
        )
        tool_messsage = f"A oferta '{target_offering.name}' está configurada para agendamento, mas não tem uma duração definida. Não consigo prosseguir."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                ]
            }
        )

    # --- 2. Lidar com Fuso Horário e Calcular Horário de Término ---
    # Assumimos um fuso horário padrão para a empresa. Idealmente, isso viria do CompanyProfile.
    # Por enquanto, vamos usar um fuso comum no Brasil.
    try:
        company_timezone = pytz.timezone("America/Sao_Paulo")
    except pytz.UnknownTimeZoneError:
        company_timezone = pytz.utc  # Fallback seguro

    # Torna o horário de início "aware" (consciente do fuso horário)
    aware_start_time = company_timezone.localize(naive_start_time)
    duration = timedelta(minutes=target_offering.duration_minutes)
    aware_end_time = aware_start_time + duration

    now_aware = datetime.now(company_timezone)
    if aware_start_time < now_aware:
        logger.warning(
            f"[{tool_name}] Attempted to schedule in the past: {appointment_datetime_str}"
        )
        tool_messsage = f"Não é possível criar um agendamento para uma data ou hora que já passou. Por favor, peça ao cliente para escolher uma data e horário futuros. Data e Horário de agora: {company_timezone}"
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                ]
            }
        )

    # --- 3. Executar o Serviço ---
    try:
        calendar_service = GoogleCalendarService()

        async with AsyncSessionLocal() as db:
            is_available = await calendar_service.is_slot_available(
                db=db,
                user_id=profile.scheduling_user_id,
                calendar_id=profile.scheduling_calendar_id,
                start_time=aware_start_time,
                end_time=aware_end_time,
                min_notice_hours=profile.scheduling_min_notice_hours,
            )

        if not is_available:
            logger.warning(
                f"Slot {aware_start_time} is no longer available. Aborting creation."
            )
            tool_messsage = "Ah, que pena! Parece que alguém acabou de agendar neste horário ou é um horário indisponível da empresa. Resumindo, Ele não está mais disponível. Poderia escolher outro da lista, por favor?"

            return Command(
                update={
                    "messages": [
                        ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                    ]
                }
            )

        event_title = f"{target_offering.name} - {customer_name or customer_email}"
        event_description = (
            f"Serviço agendado: {target_offering.name}.\n"
            f"Cliente: {customer_name}.\n"
            f"Telefone: {customer_phone}.\n"
        )

        if customer_notes:
            event_description += f"Observações: {customer_notes}"

        async with AsyncSessionLocal() as db:
            created_event = await calendar_service.create_appointment(
                db=db,
                user_id=profile.scheduling_user_id,
                calendar_id=profile.scheduling_calendar_id,
                start_time=aware_start_time,
                end_time=aware_end_time,
                title=event_title,
                description=event_description,
                attendees=[{"email": customer_email}],
            )

        event_link = created_event.get("htmlLink", "sem link")
        logger.success(
            f"[{tool_name}] Appointment successfully created. Link: {event_link}"
        )
        tool_messsage = f"Agendamento confirmado com sucesso para {aware_start_time.strftime('%d/%m/%Y às %H:%M')}! Um convite foi criado na agenda."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_messsage, tool_call_id=tool_call_id)
                ],
                "current_sales_stage": "appointment_booked",
            }
        )

    except Exception as e:
        logger.exception(f"[{tool_name}] Error creating appointment: {e}")
        error_message = "Desculpe, ocorreu um erro ao tentar confirmar seu agendamento. Por favor, tente novamente."

        return Command(
            update={
                "messages": [
                    ToolMessage(content=error_message, tool_call_id=tool_call_id)
                ]
            }
        )


@tool
async def find_next_available_day(
    offering_id_str: str,
    state: Annotated[AgentState, InjectedState],
    start_date_str: Optional[str] = None,
) -> str:
    """
    Finds the next available day with open slots for a specific service.

    Use this tool when the user asks for the next available appointment without
    specifying a date (e.g., "When can I schedule?", "What's your next opening?").
    You can optionally provide a `start_date_str` to begin the search from a
    specific day onwards (e.g., "Do you have anything next week?").

    Args:
        offering_id_str: The unique ID of the offering to find availability for.
        state: The current agent state.
        start_date_str: (Optional) The date to start searching from, in "YYYY-MM-DD"
                        format. Defaults to today if not provided.

    Returns:
        A string with the next available date in "YYYY-MM-DD" format, or a
        message indicating no availability was found within the search window.
    """
    tool_name = "find_next_available_day"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(
        f"[{tool_name}] Offering ID: '{offering_id_str}', Start Date: '{start_date_str}'"
    )

    # --- 1. Validações e Extração de Dados (similar a get_available_slots) ---
    profile = state.company_profile
    if (
        not profile
        or not profile.is_scheduling_enabled
        or not profile.scheduling_user_id
        or not profile.scheduling_calendar_id
    ):
        logger.warning(f"[{tool_name}] Scheduling is not enabled or configured.")
        return "A funcionalidade de agendamento não está configurada."

    try:
        offering_uuid = UUID(offering_id_str)
        start_date = (
            date.fromisoformat(start_date_str) if start_date_str else date.today()
        )
    except (ValueError, TypeError):
        logger.warning(f"[{tool_name}] Invalid UUID or date format.")
        return "Por favor, forneça um ID de oferta válido e, se aplicável, uma data de início válida (AAAA-MM-DD)."

    target_offering: Optional[OfferingInfo] = next(
        (o for o in profile.offering_overview if o.id == offering_uuid), None
    )

    if not target_offering or not target_offering.duration_minutes:
        logger.warning(
            f"[{tool_name}] Offering {offering_id_str} not found or has no duration."
        )
        return "A oferta selecionada não tem uma duração definida para que eu possa verificar a disponibilidade."

    # --- 2. Lógica de Busca Iterativa ---
    calendar_service = GoogleCalendarService()
    search_limit_days = (
        profile.booking_horizon_days
    )  # Limite para não buscar indefinidamente

    logger.info(
        f"[{tool_name}] Starting search for next available day from {start_date} for the next {search_limit_days} days."
    )

    try:
        async with AsyncSessionLocal() as db:
            for i in range(search_limit_days):
                current_date_to_check = start_date + timedelta(days=i)
                logger.debug(
                    f"[{tool_name}] Checking date: {current_date_to_check.isoformat()}"
                )

                # --- REUTILIZAÇÃO DE CÓDIGO ---
                # Chamamos nossa ferramenta já existente para fazer o trabalho pesado
                available_slots = await calendar_service.get_available_slots(
                    db=db,
                    user_id=profile.scheduling_user_id,
                    calendar_id=profile.scheduling_calendar_id,
                    target_date=current_date_to_check,
                    duration_minutes=target_offering.duration_minutes,
                    availability_rules=profile.availability_rules or [],
                    min_notice_hours=profile.scheduling_min_notice_hours,
                )

                if available_slots:
                    # Encontramos!
                    found_date_str = current_date_to_check.isoformat()
                    logger.success(
                        f"[{tool_name}] Found first available day: {found_date_str}"
                    )
                    return (
                        f"A próxima data com horários disponíveis é: {found_date_str}"
                    )

        # Se o loop terminar sem encontrar nada
        logger.info(
            f"[{tool_name}] No available days found within the next {search_limit_days} days."
        )
        return f"Não encontrei nenhuma disponibilidade nos próximos {search_limit_days} dias para este serviço."

    except Exception as e:
        logger.exception(f"[{tool_name}] Error during day search: {e}")
        return "Ocorreu um erro ao tentar encontrar o próximo dia disponível."


@tool
async def get_current_datetime() -> str:
    """
    Returns the current date and time, including the day of the week and timezone.

    Use this tool to know what "today", "tomorrow", "next week", etc., means.
    It provides the necessary context to translate relative time references from the
    user into specific dates (like "YYYY-MM-DD") that other tools need.
    You should call this at the beginning of any scheduling conversation if the
    user uses relative terms.

    Returns:
        A string with the current date, time, day of the week, and timezone.
        Example: "Current date and time is: 2025-06-21 15:30:00 (Saturday), Timezone: America/Sao_Paulo"
    """
    tool_name = "get_current_datetime"
    logger.info(f"--- Executing Tool: {tool_name} ---")

    # Usamos um fuso horário fixo para consistência.
    # Idealmente, isso poderia vir do CompanyProfile no futuro.
    try:
        tz = pytz.timezone("America/Sao_Paulo")
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc

    now = datetime.now(tz)

    # Formata a string de forma clara e completa para a IA.
    response_str = (
        f"Current date and time is: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({now.strftime('%A')}), Timezone: {str(tz)}"
    )

    logger.info(f"[{tool_name}] Returning: {response_str}")
    return response_str


@tool
async def find_customer_appointments(
    customer_email: str,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],  # <-- 1. Injetar o tool_call_id
) -> Command:  # <-- 2. Mudar o tipo de retorno para Command
    """
    Finds upcoming appointments for a customer. It requires the customer's email
    for verification and uses the phone number from the current conversation for security.

    Use this tool when a user asks to see, change, or cancel their appointment.
    """
    tool_name = "find_customer_appointments"
    logger.info(f"--- Executing Tool: {tool_name} (Call ID: {tool_call_id}) ---")

    customer_phone = state.customer_phone
    if not customer_phone:
        logger.warning(
            f"[{tool_name}] Customer phone number is missing from agent state."
        )
        tool_message_content = "Não consegui identificar o número de telefone desta conversa para buscar seus agendamentos com segurança."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
                ]
            }
        )

    logger.info(
        f"[{tool_name}] Verifying appointments for email '{customer_email}' associated with phone '{customer_phone}'"
    )

    profile = state.company_profile
    if (
        not profile
        or not profile.is_scheduling_enabled
        or not profile.scheduling_user_id
        or not profile.scheduling_calendar_id
    ):
        logger.warning(f"[{tool_name}] Scheduling is not enabled or fully configured.")
        tool_message_content = (
            "A funcionalidade de agendamento não está configurada para esta empresa."
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
                ]
            }
        )

    try:
        calendar_service = GoogleCalendarService()
        async with AsyncSessionLocal() as db:
            upcoming_events = await calendar_service.find_events_by_attendee(
                db=db,
                user_id=profile.scheduling_user_id,
                calendar_id=profile.scheduling_calendar_id,
                customer_phone=customer_phone,
                customer_email=customer_email,
            )

        # 3. Construir o dicionário de state_updates e a mensagem da ferramenta
        state_updates: Dict[str, Any] = {}
        tool_message_content: str

        if not upcoming_events:
            logger.info(f"[{tool_name}] No verified appointments found.")
            tool_message_content = f"Não encontrei nenhum agendamento futuro para o email {customer_email} associado a este número de telefone."
        else:
            logger.debug(f"[{tool_name}] Found Events: {upcoming_events}")

            # Atualiza o estado com os agendamentos encontrados
            state_updates["found_appointments"] = upcoming_events

            # Formata a resposta para a IA e o usuário
            response_parts = ["Encontrei os seguintes agendamentos para você:"]
            for event in upcoming_events:
                start_obj = datetime.fromisoformat(event["start"]["dateTime"])
                start_time_formatted = start_obj.strftime("%d/%m/%Y às %H:%M")
                response_parts.append(
                    f"- {event['summary']} em {start_time_formatted} (ID do Evento: {event['id']})"
                )
            response_parts.append("\nQual deles você gostaria de alterar ou cancelar?")
            tool_message_content = "\n".join(response_parts)

        # Adiciona a mensagem da ferramenta às atualizações de estado
        state_updates["messages"] = [
            ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
        ]

        # 4. Retorna o objeto Command
        return Command(update=state_updates)

    except Exception as e:
        logger.exception(f"[{tool_name}] Error finding appointments: {e}")
        error_message = (
            "Ocorreu um erro ao buscar seus agendamentos. Por favor, tente novamente."
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(content=error_message, tool_call_id=tool_call_id)
                ]
            }
        )


@tool
async def cancel_appointment(
    event_id: str,
    state: Annotated[AgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    reason: Optional[str] = None,
) -> Command:
    """
    Cancels an existing appointment using its unique Event ID.

    Use this tool only after confirming with the user which specific appointment
    (identified by its Event ID from the 'find_customer_appointments' tool)
    they wish to cancel.

    Args:
        event_id: The unique ID of the Google Calendar event to cancel.
        reason: (Optional) A brief reason for the cancellation provided by the user.
        state: The current agent state.

    Returns:
        A confirmation message indicating the result of the cancellation.
    """
    tool_name = "cancel_appointment"
    logger.info(f"--- Executing Tool: {tool_name} (Call ID: {tool_call_id}) ---")
    logger.info(f"[{tool_name}] Attempting to cancel event with ID: '{event_id}'")

    profile = state.company_profile
    if (
        not profile
        or not profile.is_scheduling_enabled
        or not profile.scheduling_user_id
        or not profile.scheduling_calendar_id
    ):
        tool_message_content = "A funcionalidade de agendamento não está configurada."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
                ]
            }
        )

    found_events = state.found_appointments
    if not found_events or not any(e.get("id") == event_id for e in found_events):
        logger.warning(
            f"[{tool_name}] Security check failed. Event ID '{event_id}' not found in state."
        )
        tool_message_content = "Erro: Para cancelar, primeiro encontre seus agendamentos e forneça o ID correto."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_message_content, tool_call_id=tool_call_id)
                ]
            }
        )

    try:
        calendar_service = GoogleCalendarService()
        async with AsyncSessionLocal() as db:
            await calendar_service.delete_event(
                db=db,
                user_id=profile.scheduling_user_id,
                calendar_id=profile.scheduling_calendar_id,
                event_id=event_id,
            )

        logger.success(f"[{tool_name}] Event {event_id} cancelled successfully.")

        updated_found_appointments = [
            e for e in found_events if e.get("id") != event_id
        ]

        state_updates = {
            "found_appointments": updated_found_appointments,
            "messages": [
                ToolMessage(
                    content="O agendamento foi cancelado com sucesso. Uma notificação de cancelamento foi enviada.",
                    tool_call_id=tool_call_id,
                )
            ],
            "current_sales_stage": "appointment_cancelled",
        }
        return Command(update=state_updates)

    except Exception as e:
        logger.error(
            f"[{tool_name}] The service layer failed to cancel appointment {event_id}: {e}"
        )
        error_message = "Ocorreu um erro ao tentar cancelar o agendamento. Por favor, tente novamente."
        if isinstance(e, HTTPException):
            error_message = f"Não foi possível cancelar o agendamento: {e.detail}"

        return Command(
            update={
                "messages": [
                    ToolMessage(content=error_message, tool_call_id=tool_call_id)
                ]
            }
        )


@tool
async def update_appointment(
    event_id: str,
    new_datetime_str: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[AgentState, InjectedState],
) -> str:
    """
    Updates (reschedules) an existing appointment to a new date and time.

    Use this tool only after:
    1. You have identified the specific event to update using its Event ID from the 'find_customer_appointments' tool.
    2. You have confirmed with the user a new, available time slot (e.g., by using 'get_available_slots').

    Args:
        event_id: The unique ID of the Google Calendar event to update.
        new_datetime_str: The new desired start time in "YYYY-MM-DD HH:MM" format.
        state: The current agent state.

    Returns:
        A confirmation message indicating the result of the rescheduling.
    """
    tool_name = "update_appointment"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(
        f"[{tool_name}] Rescheduling event '{event_id}' to '{new_datetime_str}'"
    )

    profile = state.company_profile
    if (
        not profile
        or not profile.is_scheduling_enabled
        or not profile.scheduling_user_id
        or not profile.scheduling_calendar_id
    ):
        error_message = "A funcionalidade de agendamento não está configurada."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=error_message, tool_call_id=tool_call_id)
                ]
            }
        )

    # --- VERIFICAÇÃO DE SEGURANÇA ---
    found_events = state.found_appointments
    if not found_events or not any(e.get("id") == event_id for e in found_events):
        logger.warning(
            f"[{tool_name}] Security check failed. Event ID '{event_id}' not found in state."
        )
        error_message = "Erro: Para remarcar, primeiro encontre seus agendamentos (via 'find_customer_appointments') e forneça o ID correto."
        return Command(
            update={
                "messages": [
                    ToolMessage(content=error_message, tool_call_id=tool_call_id)
                ]
            }
        )

    try:
        # --- LÓGICA DE CÁLCULO DE DURAÇÃO E HORÁRIOS ---
        original_event = next((e for e in found_events if e["id"] == event_id), None)
        if not original_event:  # Segurança extra
            error_message = "Erro interno: não foi possível encontrar os detalhes do evento original."
            return Command(
                update={
                    "messages": [
                        ToolMessage(content=error_message, tool_call_id=tool_call_id)
                    ]
                }
            )

        # Extrai os horários originais para calcular a duração
        original_start = datetime.fromisoformat(original_event["start"]["dateTime"])
        original_end = datetime.fromisoformat(original_event["end"]["dateTime"])
        duration = original_end - original_start

        # Converte a nova data/hora e aplica o fuso horário
        naive_new_start = datetime.strptime(new_datetime_str, "%Y-%m-%d %H:%M")
        company_timezone = pytz.timezone("America/Sao_Paulo")  # Assumindo fuso horário
        aware_new_start = company_timezone.localize(naive_new_start)

        # Calcula o novo horário de fim
        aware_new_end = aware_new_start + duration

        # --- CHAMADA AO SERVIÇO ---
        calendar_service = GoogleCalendarService()

        async with AsyncSessionLocal() as db:
            is_available = await calendar_service.is_slot_available(
                db=db,
                user_id=profile.scheduling_user_id,
                calendar_id=profile.scheduling_calendar_id,
                start_time=aware_new_start,
                end_time=aware_new_end,
                min_notice_hours=profile.scheduling_min_notice_hours,
                event_id_to_ignore=event_id,
            )

        if not is_available:
            logger.warning(
                f"Slot {aware_new_start} is no longer available. Aborting update."
            )
            tool_message = "Ah, que pena! Parece que este novo horário foi ocupado. Ele não está mais disponível. Por favor, peça para ver os horários livres novamente."
            return Command(
                update={
                    "messages": [
                        ToolMessage(content=tool_message, tool_call_id=tool_call_id)
                    ]
                }
            )

        async with AsyncSessionLocal() as db:
            await calendar_service.update_event_time(
                db=db,
                user_id=profile.scheduling_user_id,
                calendar_id=profile.scheduling_calendar_id,
                event_id=event_id,
                new_start_time=aware_new_start,
                new_end_time=aware_new_end,
            )

        new_time_formatted = aware_new_start.strftime("%d/%m/%Y às %H:%M")
        logger.success(
            f"[{tool_name}] Event {event_id} rescheduled successfully to {new_time_formatted}."
        )
        tool_message = f"Agendamento remarcado com sucesso para {new_time_formatted}! Os participantes foram notificados."

        return Command(
            update={
                "messages": [
                    ToolMessage(content=tool_message, tool_call_id=tool_call_id)
                ],
                "current_sales_stage": "appointment_rescheduled",
            }
        )

    except Exception as e:
        logger.exception(f"[{tool_name}] Error updating appointment: {e}")
        if isinstance(e, HTTPException):
            return f"Não foi possível remarcar o agendamento: {e.detail}"
        error_message = "Ocorreu um erro ao tentar remarcar o agendamento."

        return Command(
            update={
                "messages": [
                    ToolMessage(content=error_message, tool_call_id=tool_call_id)
                ]
            }
        )
