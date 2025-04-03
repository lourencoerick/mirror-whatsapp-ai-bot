import uuid
import secrets
from loguru import logger
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import encrypt_logical_token, decrypt_logical_token
from app.api.schemas.evolution_instance import (
    EvolutionInstanceRead,
    EvolutionInstanceQRCodeResponse,
)
from app.models.channels.evolution_instance import (
    EvolutionInstanceStatus,
    EvolutionInstance,
)
from app.services.helper.evolution_instance import (
    create_logical_evolution_instance,
    generate_connection_qrcode,
)
from app.core.dependencies.auth import get_auth_context, AuthContext
from app.services.helper.websocket import publish_to_instance_ws
from app.config import Settings, get_settings

settings: Settings = get_settings()
router = APIRouter()


@router.post(
    "/instances/evolution",
    response_model=EvolutionInstanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_evolution_instance(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> EvolutionInstance:
    """
    Handles the request to create a logical Evolution API instance associated with the authenticated account.

    Args:
        db (AsyncSession): The database session dependency.
        auth_context (AuthContext): The authentication context containing account information.

    Returns:
        EvolutionInstance: The created EvolutionInstance object with its final status.

    Raises:
        HTTPException:
            - 500: If token encryption fails.
            - 500: If the external Evolution API instance creation fails.
    """
    account_id = auth_context.account.id
    logger.info(
        f"[Account: {account_id}] Received request to create Evolution instance."
    )

    # 1. Generate Unique IDs
    platform_instance_id = uuid.uuid4()
    instance_name = str(platform_instance_id)
    logical_token = secrets.token_urlsafe(32)
    logger.info(
        f"[Account: {account_id}] [Instance: {platform_instance_id}] Generated IDs: "
        f"platform_instance_id={platform_instance_id}, instance_name={instance_name}"
    )

    # 2. Encrypt the Logical Token
    logical_token_encrypted: str
    try:
        logger.debug(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Attempting to encrypt logical token."
        )
        logical_token_encrypted = encrypt_logical_token(logical_token)
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Successfully encrypted logical token."
        )
    except Exception as e:
        logger.error(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Failed to encrypt logical token. Error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt token",
        )

    # 3. Construct the Webhook URL
    webhook_url = (
        f"{settings.BACKEND_BASE_URL}/webhooks/evolution/{platform_instance_id}"
    )
    logger.info(
        f"[Account: {account_id}] [Instance: {platform_instance_id}] Constructed webhook URL: {webhook_url}"
    )

    # 4. Create the EvolutionInstance object in the DB (Initial PENDING state)
    evolution_instance = EvolutionInstance(
        id=platform_instance_id,
        instance_name=instance_name,
        shared_api_url=settings.EVOLUTION_API_SHARED_URL,
        logical_token_encrypted=logical_token_encrypted,
        status=EvolutionInstanceStatus.PENDING,
        webhook_url=webhook_url,
        account_id=account_id,
    )
    try:
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Adding EvolutionInstance to DB with status PENDING."
        )
        db.add(evolution_instance)
        await db.commit()
        await db.refresh(evolution_instance)
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Successfully saved EvolutionInstance with PENDING status."
        )
    except Exception as e:
        logger.error(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Failed to save initial EvolutionInstance to DB. Error: {e}",
            exc_info=True,
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save instance state",
        )

    # 5. Call the service to create the *actual* Evolution instance externally
    try:
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Calling external service "
            f"create_logical_evolution_instance for instance_name: {instance_name}"
        )
        await create_logical_evolution_instance(
            instance_name=instance_name,
            logical_token=logical_token,
            webhook_url=webhook_url,
            # Add other necessary parameters if any
        )
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] External service call successful. "
            f"Updating instance status to CREATED."
        )

        evolution_instance.status = EvolutionInstanceStatus.CREATED
        db.add(evolution_instance)
        await db.commit()
        await db.refresh(evolution_instance)
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Instance status successfully updated to CREATED in DB."
        )
        await publish_to_instance_ws(
            str(platform_instance_id),
            {
                "instance_id": str(platform_instance_id),
                "status": EvolutionInstanceStatus.CREATED,
            },
        )

    except Exception as e:

        logger.error(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Call to external service "
            f"create_logical_evolution_instance failed. Error: {e}",
            exc_info=True,
        )

        try:
            logger.warning(
                f"[Account: {account_id}] [Instance: {platform_instance_id}] Attempting to update instance status to ERROR in DB."
            )
            evolution_instance.status = EvolutionInstanceStatus.ERROR
            db.add(evolution_instance)
            await db.commit()
            await db.refresh(evolution_instance)
            logger.info(
                f"[Account: {account_id}] [Instance: {platform_instance_id}] Instance status successfully updated to ERROR in DB."
            )
        except Exception as db_error:
            logger.critical(
                f"[Account: {account_id}] [Instance: {platform_instance_id}] CRITICAL: Failed to update instance status to ERROR in DB "
                f"after external service failure. DB Error: {db_error}",
                exc_info=True,
            )
            await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Evolution instance via external service. Instance ID: {platform_instance_id}",
        )

    logger.info(
        f"[Account: {account_id}] [Instance: {platform_instance_id}] Evolution instance creation process completed successfully."
    )
    return evolution_instance


@router.get(
    "/instances/evolution/{platform_instance_id}/qrcode",
    response_model=EvolutionInstanceQRCodeResponse,
)
async def get_evolution_instance_qrcode(
    platform_instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> EvolutionInstanceQRCodeResponse:
    """
    Retrieves the QR code (if available) for pairing a specific Evolution API instance,
    ensuring the instance belongs to the authenticated account.

    Args:
        platform_instance_id (uuid.UUID): The unique identifier of the Evolution instance.
        db (AsyncSession): The database session dependency.
        auth_context (AuthContext): The authentication context containing account information.

    Returns:
        EvolutionInstanceQRCodeResponse: An object containing the instance ID and the
                                         base64 encoded QR code string.

    Raises:
        HTTPException:
            - 404: If the instance is not found for the given ID and account.
            - 500: If fetching the QR code from the external Evolution API service fails.
            - 500: If the QR code data is missing or malformed in the service response.
    """
    account_id = auth_context.account.id
    logger.info(
        f"[Account: {account_id}] Received request for QR code for instance: {platform_instance_id}"
    )

    # 1. Fetch Instance Details from OUR Database
    evolution_instance: EvolutionInstance | None = None
    try:
        logger.debug(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Querying database for instance."
        )
        result = await db.execute(
            select(EvolutionInstance).filter(
                EvolutionInstance.id == platform_instance_id,
                EvolutionInstance.account_id == account_id,
            )
        )
        evolution_instance = result.scalar_one_or_none()
    except Exception as e:
        logger.error(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Database query failed. Error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while fetching instance.",
        )

    if not evolution_instance:
        logger.warning(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Instance not found or access denied."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instance with ID {platform_instance_id} not found for this account.",
        )

    logger.info(
        f"[Account: {account_id}] [Instance: {platform_instance_id}] Found instance in DB. "
        f"Instance Name: {evolution_instance.instance_name}, Status: {evolution_instance.status}"
    )

    # 2. Call the service to get the QR code
    qr_code: str | None = None
    connection_status_from_service: str = "unknown"  # Default status

    try:
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Calling external service "
            f"get_instance_connection_status for instance_name: {evolution_instance.instance_name} "
            f"at URL: {evolution_instance.shared_api_url}"
        )
        data = await generate_connection_qrcode(
            shared_url=evolution_instance.shared_api_url,
            instance_name=evolution_instance.instance_name,
            api_key=decrypt_logical_token(evolution_instance.logical_token_encrypted),
        )
        logger.info(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] External service call successful."
        )
        logger.debug(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Service response data: {data}"
        )

        qr_code = data.get("code")

        if qr_code:
            logger.info(
                f"[Account: {account_id}] [Instance: {platform_instance_id}] Successfully extracted QR code ."
            )
        else:
            logger.warning(
                f"[Account: {account_id}] [Instance: {platform_instance_id}] QR code not found in the service response. "
                f"Current status reported by service: {connection_status_from_service}"
            )

    except HTTPException as http_exc:

        logger.error(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] HTTP error during external service call. "
            f"Status: {http_exc.status_code}, Detail: {http_exc.detail}",
            exc_info=False,
        )
        raise http_exc
    except Exception as e:
        logger.error(
            f"[Account: {account_id}] [Instance: {platform_instance_id}] Failed to get QR code from external service. Error: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get QR code from external service for instance {platform_instance_id}.",
        )

    # 3. Construct and Return Response
    response_data = EvolutionInstanceQRCodeResponse(
        instance_id=str(evolution_instance.id),
        qrcode=qr_code,
        connection_status="connecting",
        detail=(
            "QR code retrieved successfully."
            if qr_code
            else "QR code not available or instance already connected."
        ),
    )
    logger.info(
        f"[Account: {account_id}] [Instance: {platform_instance_id}] Returning QR code response. "
        f"QR Present: {bool(qr_code)}, Status: {connection_status_from_service}"
    )
    return response_data
