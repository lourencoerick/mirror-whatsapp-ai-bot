import asyncio
import os
import sys
import argparse

from loguru import logger

# Set up sys.path to include project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from app.simulation.runner import run_single_simulation


async def main():
    """
    Parses command-line arguments (including optional reset flag)
    and initiates a simulation run.
    """
    parser = argparse.ArgumentParser(description="Run a single AI Seller simulation.")
    parser.add_argument(
        "persona_id",
        help="ID of the persona definition JSON file (without .json)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the conversation history before running.",
    )
    args = parser.parse_args()

    persona_id = args.persona_id
    reset_flag = args.reset  # Get reset flag value

    logger.info(f"Running simulation for Persona ID: {persona_id}")
    if reset_flag:
        logger.warning(
            "Reset flag activated: conversation history will be cleared before starting."
        )

    # Run the simulation
    try:
        await run_single_simulation(
            persona_id=persona_id,
            reset_conversation=reset_flag,  # Pass reset flag
        )
    except ValueError as ve:
        logger.error(f"Simulation setup error: {ve}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error during simulation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Entry point for CLI
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.info("Starting Simulation CLI Runner...")
    asyncio.run(main())
    logger.info("Simulation CLI Runner finished.")
