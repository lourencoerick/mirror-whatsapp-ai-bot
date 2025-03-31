from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.inbox import InboxCreate, InboxUpdate, InboxResponse
from app.services.repository import inbox as inbox_repo

router = APIRouter(prefix="", tags=["v1 - Inboxes"])


@router.get("/inboxes", response_model=List[InboxResponse])
def list_account_inboxes(
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
):
    """
    Retrieves all inboxes associated with the authenticated user's account.
    """
    account_id = auth_context.account.id
    logger.info(f"Received request to list inboxes for Account={account_id}")

    inboxes = inbox_repo.find_inboxes_by_account(
        db=db, account_id=account_id, limit=limit, offset=offset
    )
    logger.info(f"Found {len(inboxes)} inboxes for account {account_id}")
    return inboxes


# --- CREATE ---
@router.post(
    "/inboxes", response_model=InboxResponse, status_code=status.HTTP_201_CREATED
)
def create_new_inbox(
    inbox_data: InboxCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Creates a new inbox for the authenticated user's account."""
    account_id = auth_context.account.id
    logger.info(
        f"Received request to create inbox '{inbox_data.name}' for Account={account_id}"
    )
    try:
        new_inbox = inbox_repo.create_inbox(
            db=db, account_id=account_id, inbox_data=inbox_data
        )
        return new_inbox
    except Exception as e:
        logger.error(f"Failed to create inbox for Account={account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create inbox.",
        )


# --- READ (Single) ---
@router.get("/inboxes/{inbox_id}", response_model=InboxResponse)
def get_single_inbox(
    inbox_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Retrieves a specific inbox by ID, ensuring it belongs to the user's account."""
    account_id = auth_context.account.id
    logger.info(f"Received request to get Inbox ID={inbox_id} for Account={account_id}")
    inbox = inbox_repo.find_inbox_by_id_and_account(
        db=db, inbox_id=inbox_id, account_id=account_id
    )
    if not inbox:
        logger.warning(
            f"Inbox ID={inbox_id} not found or not authorized for Account={account_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox not found or not accessible",
        )
    return inbox


# --- UPDATE ---
@router.put("/inboxes/{inbox_id}", response_model=InboxResponse)
def update_existing_inbox(
    inbox_id: UUID,
    update_data: InboxUpdate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Updates an existing inbox. Ensures the inbox belongs to the user's account."""
    account_id = auth_context.account.id
    logger.info(
        f"Received request to update Inbox ID={inbox_id} for Account={account_id}"
    )
    inbox_to_update = inbox_repo.find_inbox_by_id_and_account(
        db=db, inbox_id=inbox_id, account_id=account_id
    )
    if not inbox_to_update:
        logger.warning(
            f"Update failed: Inbox ID={inbox_id} not found or not authorized for Account={account_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox not found or not accessible",
        )
    try:
        updated_inbox = inbox_repo.update_inbox(
            db=db, inbox=inbox_to_update, update_data=update_data
        )
        return updated_inbox
    except Exception as e:
        logger.error(
            f"Failed to update Inbox ID={inbox_id} for Account={account_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update inbox.",
        )


# --- DELETE ---
@router.delete("/inboxes/{inbox_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_inbox(
    inbox_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    """Deletes an existing inbox, ensuring it belongs to the user's account."""
    account_id = auth_context.account.id
    logger.info(
        f"Received request to delete Inbox ID={inbox_id} for Account={account_id}"
    )
    inbox_to_delete = inbox_repo.find_inbox_by_id_and_account(
        db=db, inbox_id=inbox_id, account_id=account_id
    )
    if not inbox_to_delete:
        logger.warning(
            f"Delete failed: Inbox ID={inbox_id} not found or not authorized for Account={account_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inbox not found or not accessible",
        )
    try:
        success = inbox_repo.delete_inbox(db=db, inbox=inbox_to_delete)
        if not success:
            raise HTTPException(status_code=500, detail="Deletion failed.")
        return None
    except Exception as e:
        logger.error(
            f"Failed to delete Inbox ID={inbox_id} for Account={account_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete inbox.",
        )
