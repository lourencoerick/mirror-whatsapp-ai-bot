# backend/app/api/routers/inboxes/api_keys.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from loguru import logger

from app.database import get_db
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.api.schemas.api_key import ApiKeyCreate, ApiKeyRead, ApiKeyReadWithSecret
from app.services.repository import inbox as inbox_repo, api_key as api_key_repo

router = APIRouter(prefix="/inboxes/{inbox_id}/api-keys", tags=["v1 - API Keys"])


@router.post(
    "", response_model=ApiKeyReadWithSecret, status_code=status.HTTP_201_CREATED
)
async def generate_new_api_key(
    inbox_id: UUID,
    key_data: ApiKeyCreate,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyReadWithSecret:
    """Generate a new API key for a specific inbox."""
    account_id = auth_context.account.id
    inbox = await inbox_repo.find_inbox_by_id_and_account(
        db, inbox_id=inbox_id, account_id=account_id
    )
    if not inbox:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Inbox not found or not accessible."
        )

    api_key_obj, raw_key = await api_key_repo.create_api_key_for_inbox(
        db, inbox=inbox, key_data=key_data
    )

    return ApiKeyReadWithSecret(
        **api_key_obj.__dict__, last_four=raw_key[-4:], raw_key=raw_key
    )


@router.get("", response_model=List[ApiKeyRead])
async def list_api_keys_for_inbox(
    inbox_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> List[ApiKeyRead]:
    """List all API keys for a specific inbox."""
    account_id = auth_context.account.id
    inbox = await inbox_repo.find_inbox_by_id_and_account(
        db, inbox_id=inbox_id, account_id=account_id
    )
    if not inbox:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Inbox not found or not accessible."
        )

    keys = await api_key_repo.get_api_keys_for_inbox(db, inbox_id=inbox_id)

    # We need to manually construct the response to include 'last_four'
    # which is not stored in the database. This is a security measure.
    # We can't get the full key here, so we'll just omit it.
    # A better approach might be to store the last_four in the DB.
    # For now, let's just show the prefix.
    response_keys = []
    for key in keys:
        key_dict = key.__dict__
        key_dict["last_four"] = "xxxx"  # Placeholder as we can't reconstruct the key
        response_keys.append(ApiKeyRead.model_validate(key_dict))

    return response_keys


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    inbox_id: UUID,
    api_key_id: UUID,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (delete) an API key."""
    account_id = auth_context.account.id
    # First, verify the user has access to the inbox
    inbox = await inbox_repo.find_inbox_by_id_and_account(
        db, inbox_id=inbox_id, account_id=account_id
    )
    if not inbox:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Inbox not found or not accessible."
        )

    # Find the specific key to delete
    key_to_delete = await db.get(api_key_repo.ApiKey, api_key_id)
    if not key_to_delete or key_to_delete.inbox_id != inbox_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API Key not found.")

    await api_key_repo.delete_api_key(db, api_key=key_to_delete)
    return None
