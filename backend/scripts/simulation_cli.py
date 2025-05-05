import asyncio
import typer

import os
import sys
import json
from uuid import UUID
from typing import Annotated, Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession


# --- Setup sys.path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------

# --- App Imports ---
from app.simulation.runner import run_single_simulation
from app.simulation.personas import generator as persona_generator
from app.simulation.personas import importer as persona_importer


from app.services.repository import (
    company_profile as profile_repo,
)
from app.models.account import Account
from app.database import AsyncSessionLocal
from app.api.schemas.company_profile import CompanyProfileSchema

from pathlib import Path

# --- Typer App ---
app = typer.Typer(
    help="CLI tool for running AI Seller simulations and managing database personas."
)

SIMULATION_ACCOUNT_ID = UUID("0c59ccfa-dc09-4a68-a1fa-d49726b2d519")


# --- Helper to Get Simulation Account ---
async def _get_simulation_account(db: AsyncSession, account_id_to_get: UUID) -> Account:
    """Fetches the simulation account object."""
    account = await db.get(Account, account_id_to_get)
    if not account:
        raise ValueError(
            f"Simulation Account with ID {account_id_to_get} not found in DB."
        )
    # Ensure simulation inbox exists? Or handle in runner/setup?
    if not account.simulation_inbox_id:
        logger.warning(
            f"Simulation account {account.id} does not have a simulation_inbox_id set."
        )
        raise ValueError(
            f"Simulation Account {account.id} missing simulation_inbox_id."
        )
    return account


@app.command(name="import-persona")
def import_persona_cli(
    json_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="Path to the JSON file containing the persona definition.",
        ),
    ],
    account_id_param: Annotated[
        Optional[UUID],
        typer.Option(
            "--account-id",
            "-a",
            help="Account ID to associate the persona/contact with (defaults to simulation account).",
        ),
    ] = None,
):
    """
    Imports a persona definition from a specified JSON file into the database.

    Validates the JSON structure, finds or creates the associated Contact based
    on 'simulation_contact_identifier' in the file, and saves the Persona record.
    """
    target_account_id = account_id_param or SIMULATION_ACCOUNT_ID
    json_file_path_str = str(json_file)

    logger.info(
        f"Executing 'import-persona' command for file: {json_file_path_str}, Account: {target_account_id}"
    )

    async def _import_wrapper():
        """Async wrapper to manage DB session and call importer."""
        async with AsyncSessionLocal() as db:
            try:
                account = await _get_simulation_account(db, target_account_id)
                logger.info(f"Using account: {account.id} for import.")
            except ValueError as e:
                logger.error(f"Setup error: {e}")
                raise

            imported_persona = await persona_importer.import_persona_from_json(
                db=db,
                account=account,
                json_file_path=json_file_path_str,
            )

            if not imported_persona:

                raise ValueError(f"Failed to import persona from {json_file_path_str}.")

            logger.success(
                f"Persona '{imported_persona.persona_id}' imported successfully from {json_file_path_str}."
            )
            print("\n--- Imported Persona ---")
            print(f"Persona ID (DB): {imported_persona.id}")
            print(f"Persona ID (Human): {imported_persona.persona_id}")
            print(f"Linked Contact ID: {imported_persona.contact_id}")
            print(
                f"Contact Identifier: {imported_persona.simulation_contact_identifier}"
            )

    try:
        asyncio.run(_import_wrapper())
    except ValueError as ve:
        logger.error(f"Error during persona import: {ve}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception(f"Unexpected error during persona import: {e}")
        raise typer.Exit(code=1)


# --- Comandos ---
@app.command()
def run(
    persona_id_str: Annotated[
        str,
        typer.Argument(
            help="The unique persona_id (string identifier) of the persona in the database."
        ),
    ],
    reset: Annotated[
        bool, typer.Option("--reset", help="Reset conversation history before running.")
    ] = False,
):
    """
    Runs a single simulation instance for the given persona ID (from Database).
    """
    logger.info(
        f"Executing 'run' command for Persona ID: {persona_id_str}, Reset: {reset}"
    )

    async def _run_sim():
        """Async wrapper to manage DB session and call runner."""
        async with AsyncSessionLocal() as db:
            try:
                account = await _get_simulation_account(db, SIMULATION_ACCOUNT_ID)
                logger.info(f"Using simulation account: {account.id}")
            except ValueError as e:
                logger.error(f"Setup error: {e}")
                raise

            await run_single_simulation(
                account=account,
                persona_id_str=persona_id_str,
                reset_conversation=reset,
            )

    try:
        asyncio.run(_run_sim())
        logger.success("Simulation run command finished.")
    except ValueError as ve:
        logger.error(f"Error during simulation run: {ve}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception(f"Unexpected error during simulation run: {e}")
        raise typer.Exit(code=1)


@app.command(name="generate-persona")
def generate_persona_cli(
    persona_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Description of the desired persona type (e.g., 'cliente curioso sobre preço').",
        ),
    ],
    account_id_param: Annotated[
        Optional[UUID],
        typer.Option(
            "--account-id",
            "-a",
            help="Account ID to base the persona on (defaults to simulation account).",
        ),
    ] = None,
    contact_identifier: Annotated[
        Optional[str],
        typer.Option(
            "--identifier",
            "-i",
            help="Optional specific contact identifier (e.g., phone number) to use/create.",
        ),
    ] = None,
):
    """
    Generates a new persona definition using an LLM, finds/creates the associated
    Contact, and saves the Persona to the DATABASE.
    """

    target_account_id = account_id_param or SIMULATION_ACCOUNT_ID
    logger.info(
        f"Executing 'generate-persona' command for Account: {target_account_id}, Type: '{persona_type}', Identifier: {contact_identifier or 'Auto'}"
    )

    async def _generate_and_save_db():
        """Async wrapper to manage DB session and call generator."""
        async with AsyncSessionLocal() as db:

            account = await db.get(Account, target_account_id)
            if not account:
                raise ValueError(f"Account {target_account_id} not found.")

            company_profile_model = await profile_repo.get_profile_by_account_id(
                db=db, account_id=target_account_id
            )
            if not company_profile_model:
                raise ValueError(
                    f"Company profile not found for account {target_account_id}"
                )
            profile_schema = CompanyProfileSchema.model_validate(company_profile_model)

            generated_persona_read = await persona_generator.generate_and_save_persona(
                db=db,
                account=account,
                profile=profile_schema,
                persona_type_description=persona_type,
                # contact_identifier=contact_identifier,
            )

            if not generated_persona_read:

                raise ValueError(
                    "Failed to generate and save persona definition to database."
                )

            logger.success(
                f"Persona '{generated_persona_read.persona_id}' generated and saved successfully to database."
            )
            print("\n--- Generated Persona ---")
            print(f"Persona ID (DB): {generated_persona_read.id}")
            print(f"Persona ID (Human): {generated_persona_read.persona_id}")
            print(f"Linked Contact ID: {generated_persona_read.contact_id}")
            print(
                f"Contact Identifier: {generated_persona_read.simulation_contact_identifier}"
            )

            print(generated_persona_read.model_dump_json(indent=2))

    try:
        asyncio.run(_generate_and_save_db())
    except ValueError as ve:
        logger.error(f"Error during persona generation/saving: {ve}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception(f"Unexpected error during persona generation/saving: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    logger.remove()

    logger.add(sys.stderr, level="DEBUG" if "--debug" in sys.argv else "INFO")
    app()
