# backend/app/api/routers/integrations.py


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from loguru import logger

from clerk_backend_api import Clerk


# Schemas
from app.api.schemas.integrations.google_calendar import (
    CalendarResponse,
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


@router.get(
    "/google/calendars",
    response_model=List[CalendarResponse],
    summary="List User's Google Calendars",
    description="Retrieves a list of Google Calendars the authenticated user has access to, enabling them to select one for scheduling.",
)
async def list_google_calendars(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    service: GoogleCalendarService = Depends(GoogleCalendarService),
):
    """
    Fetches the list of Google Calendars for the authenticated user.

    This endpoint requires the user to have already connected their Google
    account via the frontend flow with Clerk. It uses the Clerk user ID
    from the auth context to retrieve the necessary OAuth token.
    """
    user_id = auth_context.user.id  # Assumindo que AuthContext tem o user.id do Clerk

    logger.info(f"Fetching Google Calendars for Clerk user_id: {user_id}")

    if not user_id:
        # Esta verificação é redundante se get_auth_context já garante um usuário, mas é uma boa prática.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated."
        )

    try:
        calendars = await service.list_user_calendars(db=db, user_id=user_id)
        logger.info(
            f"Successfully retrieved {len(calendars)} calendars for user_id: {user_id}"
        )
        return calendars
    except HTTPException as e:
        # Re-raise HTTPExceptions from the service layer to return correct status codes
        logger.warning(
            f"Service error fetching calendars for user {user_id}: {e.detail}"
        )
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error fetching calendars for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching Google Calendars.",
        ) from e
