# app/workers/evolution_whatsapp_sync.py

import httpx
from uuid import UUID
from typing import List, Optional, Set
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from loguru import logger

# --- Local Imports ---
from app.core.security import decrypt_logical_token
from app.api.schemas.evolution_instance import EvolutionContact
from app.models.contact import Contact
from app.models.channels.evolution_instance import (
    EvolutionInstance,
)
from app.services.helper.contact import normalize_phone_number
from app.database import (
    AsyncSessionLocal,
)
from app.config import get_settings, Settings

# --- Constants ---
ARQ_TASK_NAME = "sync_evolution_whatsapp_contacts_task"


async def sync_evolution_whatsapp_contacts_task(
    ctx: dict, instance_id: UUID, account_id: UUID
):
    """
    ARQ task to fetch contacts from an Evolution WhatsApp instance
    and sync new contacts into the platform's database.

    Args:
        ctx: The ARQ job context containing dependencies like 'db' and 'httpx_client'.
        instance_id: The UUID of the WhatsApp instance to sync.

    Raises:
        Exception: Catches and logs exceptions during the process.
                   ARQ will handle retries based on worker configuration.
    """
    settings: Settings = get_settings()

    db: AsyncSession = AsyncSessionLocal()
    http_client: httpx.AsyncClient = ctx.get("httpx_client")

    if not http_client:
        http_client = httpx.AsyncClient(timeout=30.0)
        logger.warning("httpx_client not found in ARQ context, created new instance.")

    logger.info(f"[{ARQ_TASK_NAME}] Starting sync for instance_id: {instance_id}")

    api_key: Optional[str] = None

    try:
        # 1. Get Instance Details (Account ID, API Key) from DB
        instance_stmt = select(EvolutionInstance).where(
            EvolutionInstance.id == instance_id,
            EvolutionInstance.account_id == account_id,
        )
        instance_result = await db.execute(instance_stmt)
        instance = instance_result.scalars().first()

        if not instance:
            logger.error(f"[{ARQ_TASK_NAME}] Instance not found in DB: {instance_id}")
            await db.close()
            return

        api_key = decrypt_logical_token(instance.logical_token_encrypted)
        api_key = api_key if api_key is not None else settings.EVOLUTION_API_KEY

        if not api_key:
            logger.error(
                f"[{ARQ_TASK_NAME}] API key not found for instance {instance_id} or globally."
            )
            await db.close()
            return

        logger.info(
            f"[{ARQ_TASK_NAME}] Found instance {instance_id} for account {account_id}"
        )

        # 2. Fetch Contacts from Evolution API
        evolution_api_url = (
            f"{settings.EVOLUTION_API_SHARED_URL}/chat/findContacts/{instance_id}"
        )
        headers = {
            "apikey": api_key,
            "Accept": "application/json",
        }

        logger.debug(
            f"[{ARQ_TASK_NAME}] Calling Evolution API: POST {evolution_api_url}"
        )
        try:
            response = await http_client.post(evolution_api_url, headers=headers)
            response.raise_for_status()
            raw_contacts = response.json()
            logger.info(
                f"[{ARQ_TASK_NAME}] Received {len(raw_contacts)} contacts from Evolution API."
            )

        except httpx.RequestError as e:
            logger.error(
                f"[{ARQ_TASK_NAME}] HTTP request error calling Evolution API for {instance_id}: {e}"
            )
            await db.close()
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[{ARQ_TASK_NAME}] HTTP status error calling Evolution API for {instance_id}: {e.response.status_code} - {e.response.text}"
            )
            await db.close()
            raise
        except Exception as e:
            logger.error(
                f"[{ARQ_TASK_NAME}] Error processing Evolution API response for {instance_id}: {e}"
            )
            await db.close()
            raise

        # 3. Parse and Validate Evolution Contacts
        whatsapp_contacts: List[EvolutionContact] = []
        try:
            if isinstance(raw_contacts, list):
                for contact_data in raw_contacts:
                    if (
                        isinstance(contact_data.get("remoteJid"), str)
                        and "@s.whatsapp.net" in contact_data["remoteJid"]
                    ):
                        try:
                            whatsapp_contacts.append(
                                EvolutionContact.model_validate(contact_data)
                            )
                        except ValidationError as e_val:
                            logger.warning(
                                f"[{ARQ_TASK_NAME}] Skipping contact due to validation error: {e_val.errors()} | Data: {contact_data}"
                            )
            else:
                logger.warning(
                    f"[{ARQ_TASK_NAME}] Unexpected response format from Evolution API: {type(raw_contacts)}"
                )

        except Exception as e:
            logger.error(
                f"[{ARQ_TASK_NAME}] Error parsing contacts from Evolution API response: {e}"
            )

        if not whatsapp_contacts:
            logger.info(
                f"[{ARQ_TASK_NAME}] No valid contacts found or parsed from Evolution API for {instance_id}."
            )
            await db.close()
            return

        # 4. Fetch Existing Contact Phone Numbers from DB for the Account
        logger.debug(
            f"[{ARQ_TASK_NAME}] Fetching existing contact phone numbers for account {account_id}"
        )
        contact_stmt = select(Contact.identifier).where(
            Contact.account_id == account_id, Contact.deleted_at.is_(None)
        )
        active_contact_result = await db.execute(contact_stmt)

        existing_phones: Set[str] = {phone for phone, in active_contact_result.all()}
        logger.info(
            f"[{ARQ_TASK_NAME}] Found {len(existing_phones)} existing contacts in DB for account {account_id}."
        )

        # 5. Identify and Prepare New Contacts
        contacts_to_add: List[Contact] = []
        for wc in whatsapp_contacts:
            normalized_phone = normalize_phone_number(wc.phone_number)
            if not normalized_phone:
                raise ValidationError(
                    detail=f"Invalid or unparseable phone number: {wc.phone_number}",
                )

            # Ensure phone number is valid and not already in DB
            if normalized_phone and normalized_phone not in existing_phones:
                new_contact = Contact(
                    account_id=account_id,
                    phone_number=normalized_phone,
                    identifier=normalized_phone,
                    # Use display_name which prefers saved name over pushname
                    profile_picture_url=wc.profile_picture_url,
                    name=wc.display_name,
                    additional_attributes={
                        "source": "EVOLUTION_WHATSAPP_SYNC",
                        "instance_id": str(instance_id),
                    },
                )
                contacts_to_add.append(new_contact)
                # Add to existing_phones set immediately to handle duplicates within the API response itself
                existing_phones.add(normalized_phone)

        # 6. Add New Contacts to Database
        if contacts_to_add:
            logger.info(
                f"[{ARQ_TASK_NAME}] Attempting to add {len(contacts_to_add)} new contacts to DB for account {account_id}."
            )
            try:
                db.add_all(contacts_to_add)
                await db.commit()
                logger.success(
                    f"[{ARQ_TASK_NAME}] Successfully added {len(contacts_to_add)} new contacts for account {account_id}."
                )
            except Exception as e:
                logger.error(
                    f"[{ARQ_TASK_NAME}] Database error adding new contacts for account {account_id}: {e}"
                )
                await db.rollback()
        else:
            logger.info(
                f"[{ARQ_TASK_NAME}] No new contacts to add for account {account_id}."
            )

        logger.info(
            f"[{ARQ_TASK_NAME}] Finished sync successfully for instance_id: {instance_id}"
        )

    except Exception as e:
        logger.exception(
            f"[{ARQ_TASK_NAME}] Unhandled exception during sync for instance {instance_id}: {e}"
        )
        await db.rollback()
        raise
    finally:
        await db.close()
        logger.debug(
            f"[{ARQ_TASK_NAME}] DB session closed for instance_id: {instance_id}"
        )
