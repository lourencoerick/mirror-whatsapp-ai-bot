from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.inbox import InboxCreate, InboxUpdate, InboxRead
from app.services.repository import inbox as inbox_repo

router = APIRouter(prefix="", tags=["v1 - Inboxes"])


@router.get("/inboxes", response_model=List[InboxRead])
async def list_account_inboxes(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
) -> List[InboxRead]:
    """Retrieve all inboxes associated with the authenticated user's account.

    Args:
        auth_context (AuthContext): Authentication context containing user and account details.
        db (AsyncSession): Asynchronous database session.
        limit (int): Maximum number of inboxes to return.
        offset (int): Number of inboxes to skip.

    Returns:
        List[InboxRead]: A list of inboxes for the authenticated account.
    """
    account_id = auth_context.account.id
    logger.info(f"Listing inboxes with association for account {account_id}")

    results = await inbox_repo.find_inboxes_with_association_by_account(
        db=db, account_id=account_id, limit=limit, offset=offset
    )

    response_data = []
    for inbox_model, agent_id in results:
        try:
            inbox_dict = InboxRead.model_validate(inbox_model).model_dump()
        except Exception as e:
            logger.warning(
                f"Failed to validate inbox model {inbox_model.id}: {e}. Skipping."
            )
            continue
        inbox_dict["associated_bot_agent_id"] = agent_id
        response_data.append(InboxRead(**inbox_dict))

    return response_data


@router.post("/inboxes", response_model=InboxRead, status_code=status.HTTP_201_CREATED)
async def create_new_inbox(
    inbox_data: InboxCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> InboxRead:
    """Create a new inbox for the authenticated user's account.

    Args:
        inbox_data (InboxCreate): Data for creating a new inbox.
        auth_context (AuthContext): Authentication context containing user and account details.
        db (AsyncSession): Asynchronous database session.

    Returns:
        InboxRead: The newly created inbox.

    Raises:
        HTTPException: If the inbox creation fails.
    """
    account_id = auth_context.account.id
    user_id = auth_context.user.id
    logger.info(
        f"Received request to create inbox '{inbox_data.name}' for Account={account_id}"
    )
    try:
        # Automatically associate the inbox to the user creator
        new_inbox = await inbox_repo.create_inbox(
            db=db, account_id=account_id, user_id=user_id, inbox_data=inbox_data
        )
        return new_inbox
    except Exception as e:
        logger.error(f"Failed to create inbox for Account={account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create inbox.",
        )


@router.get("/inboxes/{inbox_id}", response_model=InboxRead)
async def get_single_inbox(
    inbox_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> InboxRead:
    """Retrieve a specific inbox by ID, ensuring it belongs to the authenticated account.

    Args:
        inbox_id (UUID): The ID of the inbox to retrieve.
        auth_context (AuthContext): Authentication context containing user and account details.
        db (AsyncSession): Asynchronous database session.

    Returns:
        InboxRead: The requested inbox.

    Raises:
        HTTPException: 404 if the inbox is not found or not accessible.
    """
    account_id = auth_context.account.id
    logger.info(f"Received request to get Inbox ID={inbox_id} for Account={account_id}")
    inbox = await inbox_repo.find_inbox_by_id_and_account(
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


@router.put("/inboxes/{inbox_id}", response_model=InboxRead)
async def update_existing_inbox(
    inbox_id: UUID,
    update_data: InboxUpdate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> InboxRead:
    """Update an existing inbox, ensuring it belongs to the authenticated account.

    Args:
        inbox_id (UUID): The ID of the inbox to update.
        update_data (InboxUpdate): Data for updating the inbox.
        auth_context (AuthContext): Authentication context containing user and account details.
        db (AsyncSession): Asynchronous database session.

    Returns:
        InboxRead: The updated inbox.

    Raises:
        HTTPException: 404 if the inbox is not found or not accessible.
        HTTPException: 500 if the inbox update fails.
    """
    account_id = auth_context.account.id
    logger.info(
        f"Received request to update Inbox ID={inbox_id} for Account={account_id}"
    )
    inbox_to_update = await inbox_repo.find_inbox_by_id_and_account(
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
        updated_inbox = await inbox_repo.update_inbox(
            db=db, inbox_to_update=inbox_to_update, update_data=update_data
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


@router.delete("/inboxes/{inbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_inbox(
    inbox_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an existing inbox, ensuring it belongs to the authenticated account.

    Args:
        inbox_id (UUID): The ID of the inbox to delete.
        auth_context (AuthContext): Authentication context containing user and account details.
        db (AsyncSession): Asynchronous database session.

    Returns:
        None

    Raises:
        HTTPException: 404 if the inbox is not found or not accessible.
        HTTPException: 500 if the inbox deletion fails.
    """
    account_id = auth_context.account.id
    logger.info(
        f"Received request to delete Inbox ID={inbox_id} for Account={account_id}"
    )
    inbox_to_delete = await inbox_repo.find_inbox_by_id_and_account(
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
        success = await inbox_repo.delete_inbox(db=db, inbox=inbox_to_delete)
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
