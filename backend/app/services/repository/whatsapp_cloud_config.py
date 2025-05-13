# app/services/repository/whatsapp_cloud_config_repo.py
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from loguru import logger

from app.models.channels.whatsapp_cloud_config import WhatsAppCloudConfig
from app.api.schemas.whatsapp_cloud_config import WhatsAppCloudConfigCreateInput
from app.core.security import (
    encrypt_logical_token,
)  # Assuming a generic encryption function


async def create_whatsapp_cloud_config(
    db: AsyncSession,
    account_id: UUID,
    config_data: WhatsAppCloudConfigCreateInput,
) -> WhatsAppCloudConfig:
    """Creates a new WhatsAppCloudConfig record in the database.

    Args:
        db (AsyncSession): The asynchronous database session.
        account_id (UUID): The ID of the account this configuration belongs to.
        config_data (WhatsAppCloudConfigCreateInput): The data for creating the config,
            including the raw access token.

    Returns:
        WhatsAppCloudConfig: The newly created WhatsAppCloudConfig object.

    Raises:
        ValueError: If encryption of the access token fails.
        Exception: For other database-related errors during creation.
    """
    logger.info(
        f"Attempting to create WhatsAppCloudConfig for Account ID: {account_id} "
        f"with Phone Number ID: {config_data.phone_number_id}"
    )
    try:
        encrypted_token = encrypt_logical_token(config_data.access_token)
    except Exception as e:
        logger.error(
            f"Failed to encrypt access token for Account ID: {account_id}, "
            f"Phone Number ID: {config_data.phone_number_id}. Error: {e}"
        )
        # It's crucial to not proceed if encryption fails.
        raise ValueError("Access token encryption failed.") from e

    new_config = WhatsAppCloudConfig(
        account_id=account_id,
        phone_number_id=config_data.phone_number_id,
        waba_id=config_data.waba_id,
        encrypted_access_token=encrypted_token,
        webhook_verify_token=config_data.webhook_verify_token,
        app_id=config_data.app_id,
    )

    try:
        db.add(new_config)
        await db.flush()  # Use flush to get the ID without committing the transaction yet
        await db.refresh(new_config)
        logger.info(
            f"WhatsAppCloudConfig created successfully with ID: {new_config.id} "
            f"for Account ID: {account_id}, Phone Number ID: {config_data.phone_number_id}. "
            "DB commit pending."
        )
        return new_config
    except Exception as e:
        logger.error(
            f"Database error while creating WhatsAppCloudConfig for Account ID: {account_id}, "
            f"Phone Number ID: {config_data.phone_number_id}. Error: {e}"
        )
        # The caller (e.g., inbox_repo.create_inbox) should handle rollback.
        raise


async def get_whatsapp_cloud_config_by_id(
    db: AsyncSession, config_id: UUID, account_id: UUID
) -> WhatsAppCloudConfig | None:
    """Retrieves a WhatsAppCloudConfig by its ID and account ID.

    Args:
        db (AsyncSession): The asynchronous database session.
        config_id (UUID): The ID of the WhatsAppCloudConfig to retrieve.
        account_id (UUID): The ID of the account that owns the config.

    Returns:
        Optional[WhatsAppCloudConfig]: The WhatsAppCloudConfig object if found, else None.
    """
    stmt = select(WhatsAppCloudConfig).where(
        WhatsAppCloudConfig.id == config_id,
        WhatsAppCloudConfig.account_id == account_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
