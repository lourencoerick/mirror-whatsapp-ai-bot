# backend/app/api/routers/integrations.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from loguru import logger

# Schemas
from app.api.schemas.integrations.google_calendar import (
    CalendarResponse,
)  # Criaremos este schema

# Serviços e Dependências
from app.services.google_calendar.google_calendar_service import GoogleCalendarService
from app.core.dependencies.auth import get_auth_context, AuthContext

# Define o router
router = APIRouter(
    prefix="/integrations",
    tags=["v1 - Integrations"],
)


@router.get(
    "/google/calendars",
    response_model=List[CalendarResponse],
    summary="List User's Google Calendars",
    description="Retrieves a list of Google Calendars the authenticated user has access to, enabling them to select one for scheduling.",
)
async def list_google_calendars(
    auth_context: AuthContext = Depends(get_auth_context),
    service: GoogleCalendarService = Depends(GoogleCalendarService),
):
    """
    Fetches the list of Google Calendars for the authenticated user.

    This endpoint requires the user to have already connected their Google
    account via the frontend flow with Clerk. It uses the Clerk user ID
    from the auth context to retrieve the necessary OAuth token.
    """
    clerk_user_id = (
        auth_context.user.uid
    )  # Assumindo que AuthContext tem o user.id do Clerk
    logger.info(f"Fetching Google Calendars for Clerk user_id: {clerk_user_id}")

    if not clerk_user_id:
        # Esta verificação é redundante se get_auth_context já garante um usuário, mas é uma boa prática.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated."
        )

    try:
        calendars = await service.list_user_calendars(clerk_user_id=clerk_user_id)
        logger.info(
            f"Successfully retrieved {len(calendars)} calendars for user_id: {clerk_user_id}"
        )
        return calendars
    except HTTPException as e:
        # Re-raise HTTPExceptions from the service layer to return correct status codes
        logger.warning(
            f"Service error fetching calendars for user {clerk_user_id}: {e.detail}"
        )
        raise e
    except Exception as e:
        logger.exception(
            f"Unexpected error fetching calendars for user {clerk_user_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching Google Calendars.",
        ) from e
