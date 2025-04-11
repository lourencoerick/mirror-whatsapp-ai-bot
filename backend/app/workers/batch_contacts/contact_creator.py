import os
from arq.connections import RedisSettings
from loguru import logger

from app.config import get_settings, Settings

settings: Settings = get_settings()

redis_settings = RedisSettings(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    database=settings.REDIS_DB,
)

# --- Task Definitions ---
from app.workers.batch_contacts.tasks.contact_importer import process_contact_csv_task
from app.workers.batch_contacts.tasks.evolution_whatsapp_sync import (
    sync_evolution_whatsapp_contacts_task,
)


# --- Worker Settings Class ---
# This class is used by the ARQ CLI to run the worker
class WorkerSettings:
    """ARQ Worker Configuration."""

    functions = [
        process_contact_csv_task,  # Add your task function(s) here
        sync_evolution_whatsapp_contacts_task,
    ]

    # Redis settings for the worker to connect to
    redis_settings = redis_settings

    # worker settings
    max_jobs = 10
    job_timeout = 300

    async def on_startup(ctx):
        logger.info("Worker starting up...")

    async def on_shutdown(ctx):
        logger.info("Worker shutting down...")
