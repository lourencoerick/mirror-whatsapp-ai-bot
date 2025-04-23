# backend/scripts/setup_simulation_entities.py

import asyncio
import os
import sys
from uuid import UUID
from loguru import logger
import json


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.api.schemas.inbox import InboxCreate
from app.api.schemas.company_profile import CompanyProfileSchema
from app.api.schemas.contact import ContactCreate
from app.models.conversation import ConversationStatusEnum

# --- Setup sys.path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------


# --- App Imports ---
from app.database import AsyncSessionLocal


from app.models.account import Account
from app.models.user import User
from app.services.repository import inbox as inbox_repo
from app.services.repository import contact as contact_repo
from app.services.repository import company_profile as profile_repo

from app.simulation.config import (
    SIMULATION_ACCOUNT_ID,
    SIMULATION_COMPANY_PROFILE_ID,
    SIMULATION_USER_ID,
    SIMULATION_INBOX_ID,
    SIMULATION_CONTACT_ID,
    SIMULATION_CHANNEL_ID,
    SIMULATION_ACCOUNT_NAME,
    SIMULATION_USER_NAME,
    SIMULATION_INBOX_NAME,
    SIMULATION_CONTACT_NAME,
    SIMULATION_CONTACT_PHONE_NUMBER,
)


async def setup_entities():
    """Ensures the necessary Account, Inbox, and Contact exist for simulations."""
    logger.info("Starting simulation entity setup...")
    async with AsyncSessionLocal() as db:
        try:
            # 1. Get or Create Account
            result = await db.execute(
                select(Account).filter_by(
                    id=SIMULATION_ACCOUNT_ID,
                )
            )
            account = result.scalar_one_or_none()
            if not account:
                logger.info("Account not found, creating a new one...")
                account = Account(
                    id=SIMULATION_ACCOUNT_ID, name=SIMULATION_ACCOUNT_NAME
                )
                db.add(account)
                await db.flush()
                logger.info(f"Account '{account.name}' (ID: {account.id}) ensured.")
            else:
                logger.info(
                    f"Account '{account.name}' (ID: {account.id}) already exists."
                )

            file_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "data",
                "company_profiles",
                f"padaria_central.json",
            )
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["id"] = str(SIMULATION_COMPANY_PROFILE_ID)
            profile_schema = CompanyProfileSchema(**data)

            await profile_repo.get_or_create_profile(
                db=db,
                account_id=account.id,
                profile_defaults=profile_schema.model_dump(),  # Pass defaults as dict
            )

            result = await db.execute(
                select(User).filter_by(
                    id=SIMULATION_USER_ID,
                )
            )
            user = result.scalar_one_or_none()
            if not user:
                logger.info("User not found, creating a new one...")
                user = User(
                    id=SIMULATION_USER_ID,
                    name=SIMULATION_USER_NAME,
                    uid="simulation_uid",
                    provider="simulation",
                    encrypted_password="simulation_password",
                    sign_in_count=0,
                )
                db.add(user)
                await db.flush()
                logger.info(f"User '{user.name}' (ID: {user.id}) ensured.")
            else:
                logger.info(f"User '{user.name}' (ID: {user.id}) already exists.")

            # 2. Get or Create Inbox (associated with the account)
            inbox = await inbox_repo.find_inbox_by_id_and_account(
                db=db,
                inbox_id=SIMULATION_INBOX_ID,
                account_id=account.id,
            )

            if not inbox:
                logger.info("Inbox not found, creating a new one...")

                inbox_data = InboxCreate(
                    id=SIMULATION_INBOX_ID,
                    name=SIMULATION_INBOX_NAME,
                    channel_type="evolution",
                    initial_conversation_status=ConversationStatusEnum.BOT,
                    channel_details={"id": str(SIMULATION_CHANNEL_ID)},
                    enable_auto_assignment=None,
                )

                inbox = await inbox_repo.create_inbox(
                    db=db,
                    account_id=account.id,
                    user_id=user.id,
                    inbox_data=inbox_data,
                )
                logger.info(f"Inbox '{inbox.name}' (ID: {inbox.id}) created.")
            else:
                logger.info(f"Inbox '{inbox.name}' (ID: {inbox.id}) already exists.")

            # 3. Get or Create Contact (associated with the account)

            contact = await contact_repo.find_contact_by_id(
                db=db,
                contact_id=SIMULATION_CONTACT_ID,
                account_id=account.id,
            )

            if not contact:
                logger.info("Contact not found, creating a new one...")
                contact = await contact_repo.create_contact(
                    db=db,
                    account_id=account.id,
                    contact_data=ContactCreate(
                        id=SIMULATION_CONTACT_ID,
                        name=SIMULATION_CONTACT_NAME,
                        phone_number=SIMULATION_CONTACT_PHONE_NUMBER,
                    ),
                )
                logger.info(f"Contact '{contact.name}' (ID: {contact.id}) created.")

            else:
                logger.info(
                    f"Contact '{contact.name}' (ID: {contact.id}) already exists."
                )

            # 4. Ensure ContactInbox exists (linking contact and inbox)
            # Assumes you have a repo function like this
            contact_inbox = await contact_repo.get_or_create_contact_inbox(
                db=db,
                account_id=account.id,
                contact_id=contact.id,
                inbox_id=inbox.id,
                source_id="simulation_setup",
            )

            logger.info(
                f"ContactInbox link ensured for Contact {contact.id} and Inbox {inbox.id}."
            )

            await db.commit()
            logger.success("Simulation entities setup completed successfully.")

        except Exception as e:
            logger.exception(f"Error during simulation entity setup: {e}")
            await db.rollback()
            logger.error("Setup failed, transaction rolled back.")


async def main():
    await setup_entities()


if __name__ == "__main__":
    logger.add(sys.stderr, level="INFO")
    asyncio.run(main())
