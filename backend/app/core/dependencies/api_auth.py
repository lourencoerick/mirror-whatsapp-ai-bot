# backend/app/core/dependencies/api_auth.py

from fastapi import Security, HTTPException, status, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import get_db
from app.services.api_key import key_service
from app.services.repository import api_key as api_key_repo
from app.models import Inbox

# Define the header where we expect the API key.
api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=True)


def require_scope(required_scope: str):
    """This is a dependency factory.

    It creates and returns a dependency function that verifies an API key
    and checks if it has the required scope.

    Args:
        required_scope: The permission string required to access the endpoint.

    Returns:
        A FastAPI dependency function that provides the authenticated Inbox.
    """

    async def verify_api_key_and_scope(
        raw_key: str = Security(api_key_header), db: AsyncSession = Depends(get_db)
    ) -> Inbox:
        """The actual dependency that will be executed by FastAPI."""

        # 1. Hash the incoming key to prepare for DB lookup
        hashed_key = key_service.hash_api_key(raw_key)

        # 2. Find the key in the database
        api_key_entry = await api_key_repo.find_api_key_by_hashed_key(
            db, hashed_key=hashed_key
        )

        # 3. Validate the key's existence and status
        if not api_key_entry or not api_key_entry.is_active:
            logger.warning(
                f"Authentication failed: Invalid or inactive API key provided."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or inactive API Key.",
            )

        # 4. Validate the key's permissions (scope)
        if required_scope not in api_key_entry.scopes:
            logger.warning(
                f"Authorization failed for key {api_key_entry.id}: "
                f"Missing required scope '{required_scope}'."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This API key does not have the required '{required_scope}' permission.",
            )

        # 5. If all checks pass, return the full Inbox context
        logger.info(
            f"Successfully authenticated API request for Inbox {api_key_entry.inbox_id} "
            f"with scope '{required_scope}'."
        )
        return api_key_entry.inbox

    return verify_api_key_and_scope
