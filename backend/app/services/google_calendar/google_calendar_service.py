# backend/app/services/google_calendar_service.py

import asyncio
from uuid import UUID, uuid4
from fastapi import HTTPException
from typing import Dict, List, Optional
from datetime import datetime, time, timedelta, date
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Importações do Google
import google.oauth2.credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

# Nossas importações
from app.services.repository import google_token as token_repo
from app.core.security import decrypt_logical_token
from app.config import get_settings, Settings
from app.models.company_profile import CompanyProfile
from app.models.user import User

settings: Settings = get_settings()


def _build_google_calendar_client(token: str) -> Resource:
    """
    Builds a Google Calendar API client from an OAuth access token.

    Args:
        token: The OAuth access token obtained from Clerk.

    Returns:
        A Google API client resource object ready to make calls.
    """
    credentials = google.oauth2.credentials.Credentials(token=token)
    # O 'static_discovery=False' é recomendado para evitar problemas em alguns ambientes serverless.
    return build("calendar", "v3", credentials=credentials, static_discovery=False)


class GoogleCalendarService:
    """
    A service class for handling interactions with the Google Calendar API.
    Uses the 'clerk_backend_api' library for authentication token retrieval.
    """

    def __init__(self):
        pass

    async def _get_google_token(self, db: AsyncSession, user_id: UUID) -> str:
        """
        Retrieves a valid Google OAuth access token for a user by using the
        stored refresh token.

        This method fetches the encrypted refresh token from our database,
        decrypts it, and if the access token is expired, uses the refresh
        token to obtain a new one from Google.
        """
        logger.debug(f"Getting Google token for user {user_id} from internal storage.")

        # 1. Buscar o registro do token no nosso banco de dados
        stored_token_record = await token_repo.get_google_token_by_user_id(db, user_id)
        if not stored_token_record:
            logger.error(f"No Google token record found in DB for user {user_id}.")
            raise HTTPException(
                status_code=404,
                detail="Conexão com o Google não encontrada para este usuário.",
            )

        # 2. Descriptografar o refresh token
        try:
            refresh_token = decrypt_logical_token(
                stored_token_record.encrypted_refresh_token
            )
        except Exception as e:
            logger.exception(f"Failed to decrypt refresh token for user {user_id}.")
            raise HTTPException(
                status_code=500, detail="Erro de segurança ao processar credenciais."
            ) from e

        # 3. Usar a biblioteca do Google para gerenciar o token e a renovação
        try:
            # Criamos um objeto de credenciais com as informações que temos
            credentials = Credentials(
                token=None,  # Não temos um access token inicial
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=stored_token_record.scopes,
            )

            # A mágica acontece aqui: .refresh() usa o refresh_token para obter um novo access_token
            # A biblioteca é inteligente e só fará a chamada de rede se o access_token
            # não existir ou estiver expirado.
            if not credentials.valid:
                logger.info(
                    f"Google token for user {user_id} is invalid or expired. Refreshing..."
                )
                # Usamos um Request para o transporte HTTP
                auth_request = Request()
                await asyncio.to_thread(credentials.refresh, auth_request)

            if not credentials.token:
                raise ValueError("Failed to refresh access token.")

            logger.success(
                f"Successfully obtained valid Google access token for user {user_id}."
            )
            return credentials.token

        except Exception as e:
            logger.exception(f"Failed to refresh Google token for user {user_id}: {e}")
            # Se a renovação falhar (ex: permissão revogada pelo usuário no Google),
            # o usuário precisa se reconectar.
            raise HTTPException(
                status_code=403,  # Forbidden
                detail="Não foi possível renovar a autorização com o Google. Por favor, conecte sua conta novamente.",
            ) from e

    async def list_user_calendars(
        self, db: AsyncSession, user_id: UUID
    ) -> List[Dict[str, str]]:
        """
        Asynchronously fetches the list of calendars a user has access to by
        calling the real Google Calendar API.
        """

        access_token = await self._get_google_token(db=db, user_id=user_id)
        service = _build_google_calendar_client(token=access_token)

        try:
            # A chamada de rede para o Google é I/O-bound.
            # pylint: disable=no-member
            calendar_list_request = service.calendarList().list()
            calendar_list = await asyncio.to_thread(calendar_list_request.execute)

            items = calendar_list.get("items", [])
            writable_calendars = [
                cal for cal in items if cal.get("accessRole") in ["owner", "writer"]
            ]

            return [
                {"id": cal["id"], "summary": cal["summary"]}
                for cal in writable_calendars
            ]
        except Exception as e:
            logger.exception(
                f"Google API Error listing calendars for user {user_id}: {e}"
            )
            raise HTTPException(
                status_code=502,
                detail="Falha ao se comunicar com a API do Google Calendar.",
            ) from e

    async def get_available_slots(
        self,
        db: AsyncSession,
        user_id: UUID,
        calendar_id: str,
        target_date: date,
        duration_minutes: int,
        availability_rules: List[Dict],
        min_notice_hours: float,
    ) -> List[str]:
        """
        Calculates available time slots for a specific day, ensuring slots
        for the current day are only in the future and aligned to a grid.

        Args:
            db: The async database session.
            user_id: The internal UUID of the user whose token should be used.
            calendar_id: The ID of the Google Calendar to check.
            target_date: The specific date to check for availability.
            duration_minutes: The duration of the appointment in minutes.
            availability_rules: The structured working hours from the CompanyProfile.

        Returns:
            A list of available time slots in "HH:MM" format for the company's timezone.
        """
        access_token = await self._get_google_token(db=db, user_id=user_id)
        service = _build_google_calendar_client(token=access_token)

        # 1. Determinar a regra do dia
        target_weekday = (target_date.weekday() + 1) % 7  # Converte para Domingo=0
        rule_for_day = next(
            (rule for rule in availability_rules if rule.dayOfWeek == target_weekday),
            None,
        )

        if not rule_for_day or not rule_for_day.isEnabled:
            return []

        # 2. Estabelecer o fuso horário e normalizar horários para UTC
        try:
            company_timezone = pytz.timezone("America/Sao_Paulo")
        except pytz.UnknownTimeZoneError:
            company_timezone = pytz.utc

        work_start_time = rule_for_day.startTime
        work_end_time = rule_for_day.endTime

        work_start_local = company_timezone.localize(
            datetime.combine(target_date, work_start_time)
        )
        work_end_local = company_timezone.localize(
            datetime.combine(target_date, work_end_time)
        )

        work_start_utc = work_start_local.astimezone(pytz.utc)
        work_end_utc = work_end_local.astimezone(pytz.utc)

        # 3. Chamar a API freeBusy do Google
        time_min_utc_str = datetime.combine(target_date, time.min).isoformat() + "Z"
        time_max_utc_str = datetime.combine(target_date, time.max).isoformat() + "Z"

        freebusy_body = {
            "timeMin": time_min_utc_str,
            "timeMax": time_max_utc_str,
            "items": [{"id": calendar_id}],
        }
        try:
            # pylint: disable=no-member
            freebusy_request = service.freebusy().query(body=freebusy_body)
            freebusy_result = await asyncio.to_thread(freebusy_request.execute)
            busy_intervals_data = freebusy_result["calendars"][calendar_id].get(
                "busy", []
            )
        except (HttpError, KeyError) as e:
            logger.warning(f"Google API issue or no busy data for user {user_id}: {e}")
            busy_intervals_data = []
        except Exception as e:
            logger.exception(
                f"Unexpected error getting free/busy for user {user_id}: {e}"
            )
            raise HTTPException(
                status_code=500, detail="Erro inesperado ao consultar a agenda."
            ) from e

        # 4. Calcular os slots, operando inteiramente em UTC
        available_slots = []
        now_utc = datetime.now(pytz.utc)

        # Calculamos o tempo mais cedo possível para um agendamento, uma única vez.
        earliest_booking_time_utc = now_utc + timedelta(hours=min_notice_hours)

        # O ponteiro começa no início do expediente (em UTC)
        current_slot_start_utc = work_start_utc
        appointment_duration = timedelta(minutes=duration_minutes)


        # Arredonda o horário de início para o próximo intervalo de slot (ex: 15 min)
        # para evitar oferecer horários que estão a apenas 1-2 minutos no futuro.
        slot_interval_minutes = 15
        if target_date == now_utc.date():
            minutes_past_interval = (
                current_slot_start_utc.minute % slot_interval_minutes
            )
            if minutes_past_interval > 0:
                minutes_to_add = slot_interval_minutes - minutes_past_interval
                current_slot_start_utc += timedelta(minutes=minutes_to_add)

            # Zera segundos e microssegundos para alinhamento perfeito
            current_slot_start_utc = current_slot_start_utc.replace(
                second=0, microsecond=0
            )

        busy_events_utc = [
            (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in busy_intervals_data
        ]
        all_events_utc = sorted(busy_events_utc + [(work_end_utc, work_end_utc)])

        for busy_start_utc, busy_end_utc in all_events_utc:
                free_interval_end_utc = busy_start_utc

            while current_slot_start_utc + appointment_duration <= free_interval_end_utc:
                
                # Condição 1: O slot está dentro do horário de trabalho?
                is_within_working_hours = (
                    current_slot_start_utc >= work_start_utc and
                    (current_slot_start_utc + appointment_duration) <= work_end_utc
                )
                
                # Condição 2: O slot respeita o tempo de antecedência?
                is_after_notice_period = current_slot_start_utc >= earliest_booking_time_utc

                if is_within_working_hours and is_after_notice_period:
                    # Só adicionamos o slot se AMBAS as condições forem verdadeiras
                    slot_in_company_tz = current_slot_start_utc.astimezone(company_timezone)
                    available_slots.append(slot_in_company_tz.strftime("%H:%M"))

                current_slot_start_utc += appointment_duration

            if busy_end_utc > current_slot_start_utc:
                current_slot_start_utc = busy_end_utc

        return available_slots

    async def is_slot_available(
        self,
        db: AsyncSession,
        user_id: UUID,
        calendar_id: str,
        start_time: datetime,
        end_time: datetime,
        min_notice_hours: float,
        event_id_to_ignore: Optional[str] = None,
    ) -> bool:
        """
        Checks if a specific time slot is free in a calendar.

        Args:
            db: The async database session.
            user_id: The internal UUID of the user whose token should be used.
            calendar_id: The ID of the Google Calendar to check.
            start_time: The start datetime of the slot to check (timezone-aware).
            end_time: The end datetime of the slot to check (timezone-aware).
            event_id_to_ignore: (For updates) The ID of an existing event to ignore
                                during the free/busy check.

        Returns:
            True if the slot is available, False otherwise.
        """

        now_utc = datetime.now(pytz.utc)
        earliest_booking_time_utc = now_utc + timedelta(hours=min_notice_hours)

        # O start_time que recebemos já deve ser "aware"
        if start_time < earliest_booking_time_utc:
            logger.warning(
                f"Slot availability check failed: "
                f"Start time {start_time} is before minimum notice time {earliest_booking_time_utc}."
            )
            return False 
                   
        access_token = await self._get_google_token(db=db, user_id=user_id)
        service = _build_google_calendar_client(token=access_token)

        freebusy_body = {
            "timeMin": start_time.isoformat(),
            "timeMax": end_time.isoformat(),
            "items": [{"id": calendar_id}],
        }

        try:
            # pylint: disable=no-member
            freebusy_request = service.freebusy().query(body=freebusy_body)
            freebusy_result = await asyncio.to_thread(freebusy_request.execute)
            busy_intervals = freebusy_result["calendars"][calendar_id].get("busy", [])

            # Se estamos atualizando um evento, não queremos que ele se veja como "ocupado".
            if event_id_to_ignore:
                busy_intervals = [
                    b for b in busy_intervals if b.get("id") != event_id_to_ignore
                ]

            # Se a lista de intervalos ocupados estiver vazia, o slot está livre.
            return not busy_intervals

        except Exception as e:
            logger.error(f"Error checking slot availability for user {user_id}: {e}")
            # Em caso de erro na API, assumimos por segurança que o slot NÃO está livre.
            return False

    async def create_appointment(
        self,
        user_id: UUID,
        db: AsyncSession,
        calendar_id: str,
        start_time: datetime,
        end_time: datetime,
        title: str,
        description: str,
        attendees: Optional[List[Dict[str, str]]] = None,
    ) -> Dict:
        """
        Creates a new event in the specified Google Calendar.

        Args:
            user_id: The user's ID.
            calendar_id: The ID of the calendar to create the event in.
            start_time: The start datetime of the event (timezone-aware).
            end_time: The end datetime of the event (timezone-aware).
            title: The summary/title of the event.
            description: The description for the event.

        Returns:
            A dictionary representing the created event from the Google API.
        """
        access_token = await self._get_google_token(db=db, user_id=user_id)
        service = _build_google_calendar_client(token=access_token)

        conference_data_request = {
            "createRequest": {
                "requestId": f"meet-link-{uuid4()}",  # Um ID único para a requisição
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet"  # Especifica que queremos um Google Meet
                },
            }
        }

        event_body = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": str(start_time.tzinfo),  # Envia o fuso horário
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": str(end_time.tzinfo),
            },
            "attendees": attendees or [],
            "conferenceData": conference_data_request,
        }

        try:
            # pylint: disable=no-member
            create_request = service.events().insert(
                calendarId=calendar_id,
                body=event_body,
                sendUpdates="all",
                conferenceDataVersion=1,
            )
            created_event = await asyncio.to_thread(create_request.execute)
            return created_event
        except HttpError as e:
            logger.exception(f"Google API HttpError creating event: {e}")
            raise HTTPException(
                status_code=e.resp.status,
                detail="Erro ao criar o evento no Google Calendar.",
            ) from e
        except Exception as e:
            logger.exception(f"Unexpected error creating event: {e}")
            raise HTTPException(
                status_code=500, detail="Erro inesperado ao criar o evento."
            ) from e

    async def find_events_by_attendee(
        self,
        db: AsyncSession,
        user_id: UUID,
        calendar_id: str,
        customer_phone: str,
        customer_email: str,
    ) -> List[Dict]:
        """
        Finds upcoming events by searching for the customer's phone number in
        the event description, and then verifies the attendee email for security.

        Args:
            db: The async database session.
            user_id: The internal UUID of the user whose token should be used.
            calendar_id: The ID of the Google Calendar to search in.
            customer_phone: The phone number from the conversation to search for.
            customer_email: The email provided by the user for verification.

        Returns:
            A list of verified event resource dictionaries from the Google API.
        """
        access_token = await self._get_google_token(db=db, user_id=user_id)
        service = _build_google_calendar_client(token=access_token)

        # Define o início da busca como "agora" para pegar apenas eventos futuros.
        now_utc = datetime.now(pytz.utc).isoformat()

        try:
            logger.info(
                f"Searching for events for phone '{customer_phone}' from now onwards."
            )

            # 1. Busca primária pelo telefone na descrição do evento
            # pylint: disable=no-member
            events_request = service.events().list(
                calendarId=calendar_id,
                q=customer_phone,  # Busca pelo telefone nos campos do evento
                timeMin=now_utc,  # Apenas eventos futuros
                singleEvents=True,  # Expande eventos recorrentes
                orderBy="startTime",  # Ordena os resultados pelo horário de início
                maxResults=25,  # Um limite razoável para a busca
            )

            events_result = await asyncio.to_thread(events_request.execute)
            all_found_events = events_result.get("items", [])

            # 2. Verificação secundária: filtrar os resultados para garantir que o email do convidado bate
            verified_events = []
            for event in all_found_events:
                attendees = event.get("attendees", [])
                # Verificamos se algum dos emails dos convidados corresponde ao email fornecido
                if any(
                    attendee.get("email", "").lower() == customer_email.lower()
                    for attendee in attendees
                ):
                    verified_events.append(event)

            logger.info(
                f"Found {len(verified_events)} verified upcoming event(s) for phone '{customer_phone}' and email '{customer_email}'."
            )
            return verified_events

        except HttpError as e:
            logger.exception(
                f"Google API HttpError finding events for {customer_email}: {e}"
            )
            raise HTTPException(
                status_code=e.resp.status,
                detail="Erro ao buscar agendamentos no Google Calendar.",
            ) from e
        except Exception as e:
            logger.exception(
                f"Unexpected error finding events for {customer_email}: {e}"
            )
            raise HTTPException(
                status_code=500, detail="Erro inesperado ao buscar agendamentos."
            ) from e

    async def delete_event(
        self,
        db: AsyncSession,
        user_id: UUID,
        calendar_id: str,
        event_id: str,
    ) -> None:
        """
        Deletes an event from a specified Google Calendar.

        Args:
            db: The async database session.
            user_id: The internal UUID of the user whose token should be used.
            calendar_id: The ID of the Google Calendar containing the event.
            event_id: The unique ID of the event to be deleted.

        Returns:
            None. Raises an exception on failure.
        """
        access_token = await self._get_google_token(db=db, user_id=user_id)
        service = _build_google_calendar_client(token=access_token)

        try:
            logger.info(
                f"Attempting to delete event '{event_id}' from calendar '{calendar_id}'."
            )

            # pylint: disable=no-member
            delete_request = service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates="all",  # Notifica todos os participantes sobre o cancelamento
            )

            await asyncio.to_thread(delete_request.execute)

            logger.success(f"Successfully deleted event '{event_id}'.")

        except HttpError as e:
            # Se o evento já foi deletado ou não existe, o Google retorna 404 ou 410.
            # Podemos tratar isso como um "sucesso" para não confundir o usuário.
            if e.resp.status in [404, 410]:
                logger.warning(
                    f"Event '{event_id}' not found or already gone. Treating as success."
                )
                return

            logger.exception(f"Google API HttpError deleting event {event_id}: {e}")
            raise HTTPException(
                status_code=e.resp.status,
                detail="Erro ao cancelar o evento no Google Calendar.",
            ) from e
        except Exception as e:
            logger.exception(f"Unexpected error deleting event {event_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Erro inesperado ao cancelar o agendamento."
            ) from e

    async def update_event_time(
        self,
        db: AsyncSession,
        user_id: UUID,
        calendar_id: str,
        event_id: str,
        new_start_time: datetime,
        new_end_time: datetime,
    ) -> Dict:
        """
        Updates the start and end time of an existing event in a Google Calendar.

        Args:
            db: The async database session.
            user_id: The internal UUID of the user whose token should be used.
            calendar_id: The ID of the Google Calendar containing the event.
            event_id: The unique ID of the event to be updated.
            new_start_time: The new start datetime for the event (timezone-aware).
            new_end_time: The new end datetime for the event (timezone-aware).

        Returns:
            A dictionary representing the updated event from the Google API.
        """
        access_token = await self._get_google_token(db=db, user_id=user_id)
        service = _build_google_calendar_client(token=access_token)

        # O corpo do 'patch' contém apenas os campos que queremos alterar.
        update_body = {
            "start": {
                "dateTime": new_start_time.isoformat(),
                "timeZone": str(new_start_time.tzinfo),
            },
            "end": {
                "dateTime": new_end_time.isoformat(),
                "timeZone": str(new_end_time.tzinfo),
            },
        }

        try:
            logger.info(
                f"Attempting to update event '{event_id}' to start at '{new_start_time}'."
            )

            # pylint: disable=no-member
            patch_request = service.events().patch(
                calendarId=calendar_id,
                eventId=event_id,
                body=update_body,
                sendUpdates="all",  # Notifica os participantes sobre a alteração
            )

            updated_event = await asyncio.to_thread(patch_request.execute)

            logger.success(f"Successfully updated event '{event_id}'.")
            return updated_event

        except HttpError as e:
            logger.exception(f"Google API HttpError updating event {event_id}: {e}")
            raise HTTPException(
                status_code=e.resp.status,
                detail="Erro ao remarcar o evento no Google Calendar.",
            ) from e
        except Exception as e:
            logger.exception(f"Unexpected error updating event {event_id}: {e}")
            raise HTTPException(
                status_code=500, detail="Erro inesperado ao remarcar o agendamento."
            ) from e
