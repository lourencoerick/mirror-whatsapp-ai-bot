# backend/app/api/routers/integrations.py


from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from clerk_backend_api import Clerk


# Schemas
from app.api.schemas.integrations.google_calendar import (
    GoogleIntegrationStatus,
)

# Serviços e Dependências
from app.services.google_calendar.google_calendar_service import GoogleCalendarService
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.database import get_db

from app.config import get_settings, Settings

settings: Settings = get_settings()
# Define o router
router = APIRouter(
    prefix="/integrations",
    tags=["v1 - Integrations"],
)


@router.get(
    "/google/status",
    response_model=GoogleIntegrationStatus,
    summary="Get Google Integration Status",
    tags=["Google Integration"],
)
async def get_google_integration_status(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Checks the full status of the Google integration for the current user,
    including connection status, permission scopes, and available calendars.
    """
    user_id = auth_context.user.id
    clerk_user_id = auth_context.user.uid  # Assumindo que o uid é o clerk_id

    try:
        # Usamos o async with para segurança de recursos
        async with Clerk(bearer_auth=settings.CLERK_SECRET_KEY) as clerk:
            # Este método busca o token e os escopos associados
            token_data_list = await clerk.users.get_o_auth_access_token_async(
                user_id=clerk_user_id, provider="google"
            )

        if not token_data_list:
            return GoogleIntegrationStatus(
                is_connected=False, has_all_permissions=False
            )

        token_info = token_data_list[0]
        granted_scopes = set(token_info.scopes or [])

        # --- A VERIFICAÇÃO DE PERMISSÃO ---
        required_scopes = {
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
        }

        has_all_permissions = required_scopes.issubset(granted_scopes)

        if not has_all_permissions:
            logger.warning(f"User {user_id} is missing required Google scopes.")
            return GoogleIntegrationStatus(is_connected=True, has_all_permissions=False)

        # Se todas as permissões estiverem lá, buscamos os calendários
        calendar_service = GoogleCalendarService()

        calendars = await calendar_service.list_user_calendars(db=db, user_id=user_id)

        return GoogleIntegrationStatus(
            is_connected=True, has_all_permissions=True, calendars=calendars
        )

    except Exception as e:
        logger.exception(
            f"Error getting Google integration status for user {user_id}: {e}"
        )
        return GoogleIntegrationStatus(
            is_connected=True,  # A conexão existe, mas algo deu errado
            has_all_permissions=False,
            error_message=str(e),
        )
