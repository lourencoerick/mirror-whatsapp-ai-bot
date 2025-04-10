import os
from arq.connections import RedisSettings
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file (optional)
load_dotenv()

# --- Redis Configuration ---
# Use environment variables for flexibility
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)  # Optional password

redis_settings = RedisSettings(
    host=REDIS_HOST,
    port=REDIS_PORT,
    database=REDIS_DB,
    password=REDIS_PASSWORD,
    # Add other settings like ssl=True if needed
)

# --- Task Definitions ---
# Import the actual task function(s) defined elsewhere (e.g., tasks.py)
from app.workers.batch_contacts.tasks import process_contact_csv_task  # Example import

# --- Constants ---
# Define the task name constant if you use it in the API router
ARQ_TASK_NAME = "process_contact_csv_task"  # Ensure this matches the function name or registered name


# --- Worker Settings Class ---
# This class is used by the ARQ CLI to run the worker
class WorkerSettings:
    """ARQ Worker Configuration."""

    # List of functions that the worker should be able to execute
    # Make sure the actual task function is included here
    functions = [
        process_contact_csv_task,  # Add your task function(s) here
        # other_task_function,
    ]

    # Redis settings for the worker to connect to
    redis_settings = redis_settings

    # Optional: Add other worker settings like max_jobs, job_timeout, etc.
    max_jobs = 10
    job_timeout = 300  # 5 minutes

    # Optional: Define on_startup and on_shutdown coroutines for the worker itself
    async def on_startup(ctx):
        logger.info("Worker starting up...")

    async def on_shutdown(ctx):
        logger.info("Worker shutting down...")
