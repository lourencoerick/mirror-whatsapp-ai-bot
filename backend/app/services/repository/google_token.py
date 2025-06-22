# backend/app/services/repository/google_token.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from typing import List, Optional
from loguru import logger

from app.models.google_oauth_token import GoogleOAuthToken


async def upsert_google_token(
    db: AsyncSession, user_id: UUID, encrypted_refresh_token: bytes, scopes: List[str]
) -> GoogleOAuthToken:
    """
    Creates a new GoogleOAuthToken record for a user or updates an existing one.

    This function performs an "upsert" operation:
    - If a token record for the given user_id already exists, it updates the
      refresh_token and scopes.
    - If no record exists, it creates a new one.

    Args:
        db: The async database session.
        user_id: The internal UUID of the user.
        encrypted_refresh_token: The encrypted refresh token in bytes.
        scopes: The list of granted OAuth scopes.

    Returns:
        The created or updated GoogleOAuthToken ORM instance.
    """
    logger.debug(f"Upserting Google OAuth token for user_id: {user_id}")

    # 1. Tenta encontrar um token existente para este usuário
    stmt = select(GoogleOAuthToken).where(GoogleOAuthToken.user_id == user_id)
    result = await db.execute(stmt)
    existing_token = result.scalar_one_or_none()

    if existing_token:
        # 2. Se existir, atualiza o token e os escopos
        logger.info(f"Found existing token for user {user_id}. Updating it.")
        existing_token.encrypted_refresh_token = encrypted_refresh_token
        existing_token.scopes = scopes
        db.add(existing_token)
        await db.flush()  # Aplica a mudança na sessão
        await db.refresh(existing_token)  # Recarrega o objeto com os dados do DB
        return existing_token
    else:
        # 3. Se não existir, cria um novo registro
        logger.info(f"No existing token found for user {user_id}. Creating a new one.")
        new_token = GoogleOAuthToken(
            user_id=user_id,
            encrypted_refresh_token=encrypted_refresh_token,
            scopes=scopes,
        )
        db.add(new_token)
        await db.flush()  # Aplica a mudança na sessão
        await db.refresh(new_token)  # Recarrega o objeto com os dados do DB
        return new_token


async def get_google_token_by_user_id(
    db: AsyncSession, user_id: UUID
) -> Optional[GoogleOAuthToken]:
    """
    Retrieves a GoogleOAuthToken record for a specific user.

    Args:
        db: The async database session.
        user_id: The internal UUID of the user.

    Returns:
        The GoogleOAuthToken ORM instance if found, otherwise None.
    """
    stmt = select(GoogleOAuthToken).where(GoogleOAuthToken.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
