from datetime import datetime, timezone
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from svix.webhooks import Webhook
from loguru import logger

from app.config import Settings, get_settings
from app.database import get_db
from app.models.account import Account
from app.models.account_user import AccountUser, UserRole

from app.models.user import User

from app.simulation.setup_service import setup_simulation_environment

router = APIRouter(prefix="/webhooks", tags=["Webhooks Clerk"])


def _get_primary_email(data: dict) -> str | None:
    """Extracts the primary email address from Clerk user data."""
    email_data = data.get("email_addresses", [])
    primary_email_id = data.get("primary_email_address_id")
    if not email_data or not primary_email_id:
        return None
    return next(
        (e.get("email_address") for e in email_data if e.get("id") == primary_email_id),
        None,
    )


async def process_user_created(data: dict, db: AsyncSession):
    """Processes the 'user.created' event from Clerk webhook (asynchronous DB, Loguru logging)."""
    clerk_user_id = data.get("id")
    primary_email = _get_primary_email(data)
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    user_name = (
        f"{first_name or ''} {last_name or ''}".strip()
        or primary_email
        or clerk_user_id
    )

    if not clerk_user_id:
        logger.error("Missing 'id' (clerk_user_id) in user.created event data.")
        return

    if not primary_email:
        logger.warning(
            f"Missing 'primary_email' in user.created event for clerk_id: {clerk_user_id}. Proceeding without email."
        )

    logger.info(
        f"Processing user.created for Clerk ID: {clerk_user_id}, Email: {primary_email}"
    )

    try:
        stmt_select = select(User).where(
            User.provider == "clerk", User.uid == clerk_user_id
        )
        result = await db.execute(stmt_select)
        existing_user = result.scalars().first()

        if not existing_user:
            logger.info(
                f"User {clerk_user_id} not found. Creating new user and account."
            )

            account_name = f"Conta de {user_name}"
            new_account = Account(name=account_name)
            db.add(new_account)
            await db.flush()

            logger.info(
                f"Created Account ID: {new_account.id} for Clerk User: {clerk_user_id}"
            )

            new_user = User(
                provider="clerk",
                uid=clerk_user_id,
                email=primary_email,
                name=user_name,
                encrypted_password="clerk_managed",
                confirmed_at=datetime.now(timezone.utc),
                sign_in_count=0,
            )
            db.add(new_user)
            await db.flush()

            logger.info(
                f"Created User ID: {new_user.id} for Clerk User: {clerk_user_id}"
            )

            default_role = UserRole.ADMIN
            account_user_link = AccountUser(
                user_id=new_user.id,
                account_id=new_account.id,
                role=default_role,
            )
            db.add(account_user_link)

            logger.info(
                f"Linking User {new_user.id} to Account {new_account.id} with role '{default_role}'"
            )

            # -- Creating Simulation environment --
            try:
                logger.info(
                    f"Attempting to set up simulation environment for Account {new_account.id}..."
                )

                sim_inbox, sim_contact, sim_convo = await setup_simulation_environment(
                    session=db, account=new_account, user=new_user
                )
                logger.info(
                    f"Simulation environment setup successful for Account {new_account.id}. "
                    f"Inbox: {sim_inbox.id}, Contact: {sim_contact.id}, Conversation: {sim_convo.id}"
                )
            except Exception as sim_error:
                logger.error(
                    f"Failed to set up simulation environment for Account {new_account.id} "
                    f"(User: {new_user.id}). Account/User creation will proceed. Error: {sim_error}",
                    exc_info=True,  # Include stack trace
                )
                # Raise exception to trigger rollback
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"User/Account created, but simulation setup failed: {sim_error}",
                ) from sim_error

            await db.commit()

            logger.info(
                f"Successfully created and linked User {new_user.id} and Account {new_account.id} for Clerk ID {clerk_user_id}."
            )

        else:

            logger.warning(
                f"User with provider 'clerk' and uid {clerk_user_id} already exists (User ID: {existing_user.id}). Skipping creation."
            )

    except Exception as e:
        logger.exception(
            f"Database error processing user.created for Clerk ID {clerk_user_id}"
        )
        await db.rollback()


@router.post("/clerk", status_code=status.HTTP_200_OK, include_in_schema=False)
async def handle_clerk_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
):
    """Handles incoming webhooks from Clerk (asynchronous DB, Loguru logging)."""
    webhook_secret = settings.CLERK_WEBHOOK_SECRET
    if not webhook_secret:
        logger.error("CLERK_WEBHOOK_SECRET is not configured in settings.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured.",
        )

    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")
    svix_signature = request.headers.get("svix-signature")
    logger.debug(
        f"Received Svix Headers - ID: '{svix_id}', Timestamp: '{svix_timestamp}', Signature: '{svix_signature}'"
    )

    if not all([svix_id, svix_timestamp, svix_signature]):
        logger.warning("Webhook request missing required Svix headers.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required Svix headers.",
        )

    payload_bytes = await request.body()

    try:
        wh = Webhook(webhook_secret)
        payload = wh.verify(
            payload_bytes,
            {
                "svix-id": svix_id,
                "svix-timestamp": svix_timestamp,
                "svix-signature": svix_signature,
            },
        )
        event_type = payload.get("type", "unknown")
        logger.info(f"Clerk Webhook verified successfully. Type: {event_type}")

    except Exception as e:
        logger.error(f"Clerk Webhook verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        ) from e

    event_data = payload.get("data")
    if not event_data:
        logger.warning(
            f"Webhook payload missing 'data' field for event type {event_type}"
        )
        return {"message": "Webhook received but no data to process."}

    if event_type == "user.created":
        await process_user_created(event_data, db)
    # elif event_type == "user.updated":
    #     process_user_updated(event_data, db, settings)
    else:
        logger.info(f"Received unhandled Clerk event type: {event_type}")

    return {"message": "Webhook received"}
