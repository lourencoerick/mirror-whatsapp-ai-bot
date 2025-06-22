# backend/app/api/routers/integrations.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

# Schemas
from app.api.schemas.integrations.google_calendar import GoogleIntegrationStatus

# Serviços, Repositórios e Dependências
from app.services.google_calendar.google_calendar_service import GoogleCalendarService
from app.services.repository import (
    google_token as token_repo,
)  # Repositório para buscar o token
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.database import get_db
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/integrations", tags=["v1 - Integrations"])


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
    Checks the status of the Google integration for the current user by
    querying our internal token storage.
    """
    user_id = auth_context.user.id
    logger.info(f"Checking Google integration status for user: {user_id}")

    try:
        # 1. Busca o token no NOSSO banco de dados
        stored_token = await token_repo.get_google_token_by_user_id(
            db=db, user_id=user_id
        )

        if not stored_token:
            logger.info(f"No stored Google token found for user {user_id}.")
            return GoogleIntegrationStatus(
                is_connected=False, has_all_permissions=False
            )

        # 2. Se o token existe, a conexão está feita. Agora verificamos as permissões.
        granted_scopes = set(stored_token.scopes or [])
        required_scopes = set(
            settings.GOOGLE_AUTH_SCOPES
        )  # Pega os escopos da nossa config

        has_all_permissions = required_scopes.issubset(granted_scopes)

        if not has_all_permissions:
            logger.warning(
                f"User {user_id} is missing required Google scopes. "
                f"Has: {granted_scopes}, Needs: {required_scopes}"
            )
            return GoogleIntegrationStatus(is_connected=True, has_all_permissions=False)

        # 3. Se tem todas as permissões, busca os calendários
        logger.info(f"User {user_id} has all required permissions. Fetching calendars.")
        calendar_service = GoogleCalendarService()
        calendars = await calendar_service.list_user_calendars(db=db, user_id=user_id)

        return GoogleIntegrationStatus(
            is_connected=True, has_all_permissions=True, calendars=calendars
        )

    except Exception as e:
        logger.exception(
            f"Error getting Google integration status for user {user_id}: {e}"
        )
        # Retornamos um estado "desconectado" em caso de erro inesperado para forçar uma nova conexão.
        return GoogleIntegrationStatus(
            is_connected=False,
            has_all_permissions=False,
            error_message=str(e),
        )
