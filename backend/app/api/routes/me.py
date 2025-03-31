from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from loguru import logger
from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.services.repository import inbox as inbox_repo
from app.api.schemas.inbox import InboxResponse


router = APIRouter(prefix="/me", tags=["v1 - Current User"])


@router.get("/inboxes", response_model=List[InboxResponse])
def get_my_inboxes(
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """
    Returns all inboxes the CURRENT authenticated user is a member of
    within their active account.
    """
    user_id = auth_context.user.id
    account_id = auth_context.account.id
    logger.info(
        f"Finding inboxes for current user (ID={user_id}) in Account={account_id}"
    )
    inboxes = inbox_repo.find_inboxes_by_user_membership(
        db=db, account_id=account_id, user_id=user_id
    )
    return inboxes
