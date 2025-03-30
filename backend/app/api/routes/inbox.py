from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from loguru import logger
from app.database import get_db
from app.core.dependencies import get_auth_context, AuthContext
from app.middleware.user_context import get_user_id_from_header
from app.services.repository.inbox import find_all_by_user
from app.api.schemas.inbox import InboxResponse

router = APIRouter()


@router.get("/inboxes", response_model=List[InboxResponse])
def get_user_inboxes(
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    """
    Returns all inboxes that the current user has access to within the current account.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id

    inboxes = find_all_by_user(db=db, account_id=account_id, user_id=user_id)
    if inboxes:
        logger.info(f"Found inboxes: {inboxes}")
    else:
        logger.info(f"No found inboxes")
    return inboxes
