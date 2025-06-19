# backend/app/services/google_calendar_service.py

from fastapi import HTTPException
from typing import Dict, List

from clerk_backend_api import Clerk
from app.config import get_settings, Settings

settings: Settings = get_settings()


class GoogleCalendarService:
    """
    A service class for handling interactions with the Google Calendar API.
    Uses the 'clerk_backend_api' library for authentication token retrieval.
    """

    def __init__(self):
        """Initializes the service and its infrastructure clients."""
        self.clerk_client = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)

    async def _get_google_token(self, clerk_user_id: str) -> str:
        """
        Retrieves the Google OAuth access token for a user from Clerk
        using the clerk_backend_api library.
        """
        try:
            # A sintaxe correta para obter tokens OAuth com esta biblioteca
            # é através do método 'users.get_oauth_access_token'.
            # O nome do provedor deve ser 'google' em minúsculas.
            token_list = await self.clerk_client.users.get_o_auth_access_token_async(
                user_id=clerk_user_id, provider="google"
            )

            if not token_list:
                raise HTTPException(
                    status_code=404,
                    detail="Token do Google não encontrado. O usuário precisa conectar sua conta do Google.",
                )

            # A resposta é uma lista de dicionários.
            # Precisamos extrair o token do primeiro item.
            token_info = token_list[0]
            access_token = token_info.token

            if not access_token:
                raise HTTPException(
                    status_code=404,
                    detail="Token de acesso não encontrado na resposta do Clerk.",
                )

            return access_token
        except HTTPException as e:
            raise e
        except Exception as e:
            print(f"Error fetching token from Clerk for user {clerk_user_id}: {e}")
            raise HTTPException(
                status_code=403,
                detail="Não foi possível obter o token do Google. A permissão pode ter sido revogada.",
            ) from e

    async def list_user_calendars(self, clerk_user_id: str) -> List[Dict[str, str]]:
        """
        Fetches the list of calendars a user has access to.
        (The logic of this method remains unchanged).
        """
        access_token = await self._get_google_token(clerk_user_id=clerk_user_id)

        # --- MOCK IMPLEMENTATION (continua igual) ---
        print(f"SERVICE: Successfully retrieved token for user {clerk_user_id}.")
        print("SERVICE: Simulating a call to Google Calendar API to list calendars...")

        mock_calendars = [
            {"id": "joao.silva@exemplo.com", "summary": "João da Silva (Pessoal)"},
            {
                "id": "c_1a2b3c4d5e@group.calendar.google.com",
                "summary": "Agenda da Barbearia",
            },
            {
                "id": "en.brazilian#holiday@group.v.calendar.google.com",
                "summary": "Feriados no Brasil",
            },
        ]
        return mock_calendars
