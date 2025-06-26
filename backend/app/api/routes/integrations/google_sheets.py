# backend/app/api/routers/integrations/sheets.py

from fastapi import APIRouter, Depends, status
from loguru import logger

from app.api.schemas.integrations.google_sheets import SheetsTriggerPayload
from app.core.dependencies.api_auth import require_scope
from app.models import Inbox

# Create a new router for sheet integrations
router = APIRouter()

# Define the scope required for this endpoint
SHEETS_TRIGGER_SCOPE = "sheets:trigger"


@router.post(
    "/sheets/trigger-conversation",
    summary="Trigger a Conversation from Google Sheets",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_from_sheets(
    payload: SheetsTriggerPayload,
    current_inbox: Inbox = Depends(require_scope(SHEETS_TRIGGER_SCOPE)),
):
    """
    Receives a webhook from a configured Google Sheet to start a new
    conversation with a contact via a specific Inbox.

    This endpoint is secured by an API key which must have the
    `sheets:trigger` scope.
    """
    company = current_inbox.company_profile
    logger.info(
        f"Accepted Sheets trigger for Company '{company.company_name}' "
        f"via Inbox '{current_inbox.name}'. "
        f"Target contact: {payload.contact_phone}"
    )

    # TODO: This is where we will call the core AI service
    # to actually start the WhatsApp conversation.
    # For example:
    # await conversation_service.initiate_from_trigger(
    #     inbox=current_inbox,
    #     payload=payload,
    # )

    return {
        "status": "accepted",
        "detail": "Conversation trigger has been accepted and is being processed.",
        "inbox_id": current_inbox.id,
        "contact_phone": payload.contact_phone,
    }
