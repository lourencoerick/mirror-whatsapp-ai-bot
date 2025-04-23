import asyncio
import typer
import os
import sys
from uuid import UUID
from typing_extensions import Annotated
from loguru import logger


# --- Setup sys.path ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------

# --- App Imports ---

from app.simulation.runner import run_single_simulation
from app.simulation.personas import generator as persona_generator
from app.simulation.personas import loader as persona_loader
from app.services.repository import (
    company_profile as profile_repo,
)
from app.database import AsyncSessionLocal
from app.api.schemas.company_profile import CompanyProfileSchema
from app.simulation.config import SIMULATION_ACCOUNT_ID, PERSONA_DIR

# --- Typer App ---
app = typer.Typer(
    help="CLI tool for running AI Seller simulations and managing personas."
)

# --- Comandos ---


@app.command()
def run(
    persona_id: Annotated[
        str,
        typer.Argument(help="ID of the persona definition JSON file (without .json)."),
    ],
    reset: Annotated[
        bool, typer.Option("--reset", help="Reset conversation history before running.")
    ] = False,
):
    """
    Runs a single simulation instance for the given persona ID.
    """
    logger.info(f"Executing 'run' command for Persona ID: {persona_id}, Reset: {reset}")
    try:
        asyncio.run(
            run_single_simulation(persona_id=persona_id, reset_conversation=reset)
        )
        logger.success("Simulation run completed.")
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
        typer.Option("--type", "-t", help="Description of the desired persona type."),
    ],
    account_id: Annotated[
        UUID,
        typer.Option("--account-id", "-a", help="Account ID to base the persona on."),
    ] = SIMULATION_ACCOUNT_ID,
    output_dir: Annotated[
        str,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory to save the generated persona JSON file.",
        ),
    ] = PERSONA_DIR,
):
    """
    Generates a new persona definition using an LLM based on a company profile
    and saves it as a JSON file.
    """
    logger.info(
        f"Executing 'generate-persona' command for Account: {account_id}, Type: '{persona_type}'"
    )

    async def _generate_and_save():
        async with AsyncSessionLocal() as db:
            company_profile_model = await profile_repo.get_profile_by_account_id(
                db=db, account_id=account_id
            )
            if not company_profile_model:
                raise ValueError(f"Company profile not found for account {account_id}")
            profile_schema = CompanyProfileSchema.model_validate(company_profile_model)

        generated_persona = await persona_generator.generate_persona_definition(
            profile=profile_schema, persona_type_description=persona_type
        )

        if not generated_persona:
            raise ValueError("Failed to generate persona definition")

        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Created output directory: {output_dir}")

            file_path = os.path.join(output_dir, f"{generated_persona.persona_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json_str = generated_persona.model_dump_json(indent=4)
                f.write(json_str)
            logger.success(f"Persona definition saved successfully to: {file_path}")
            print(f"\nGenerated Persona ID: {generated_persona.persona_id}")
            print(f"Saved to: {file_path}")

        except Exception as e:
            logger.exception(f"Failed to save generated persona to file: {e}")
            raise

    try:
        asyncio.run(_generate_and_save())
    except ValueError as ve:
        logger.error(f"Error during persona generation: {ve}")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.exception(f"Unexpected error during persona generation: {e}")
        raise typer.Exit(code=1)


@app.command(name="setup-entities")
def setup_entities_cli():
    """
    Ensures the necessary Account, Inbox, Contacts, and ContactInboxes exist
    in the database for running simulations based on persona files.
    """
    logger.info("Executing 'setup-entities' command...")
    try:
        from scripts.simulation.setup_simulation_entities import (
            setup_entities,
        )

        asyncio.run(setup_entities())
        logger.success("Entity setup command finished.")
    except Exception as e:
        logger.exception(f"Error during entity setup: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    app()
