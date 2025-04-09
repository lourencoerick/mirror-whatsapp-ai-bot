# app/core/arq_manager.py

import redis.asyncio as redis
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from typing import Optional
from loguru import logger

# Import redis_settings from your worker configuration file
# Adjust the import path based on where your worker.py/WorkerSettings class is defined
# Example: from app.workers.contact_importer import redis_settings
# Example: from app.worker import redis_settings
from app.workers.batch_contacts.contact_importer import (
    redis_settings,
)  # Adjust this import path!

# Global variable to hold the ARQ Redis pool instance
# Using Optional[ArqRedis] for type hinting
_arq_redis_pool: Optional[ArqRedis] = None


async def init_arq_pool() -> ArqRedis:
    """
    Initializes the ARQ Redis connection pool.
    Should ideally be called during application startup (e.g., FastAPI lifespan).
    """
    global _arq_redis_pool
    if _arq_redis_pool is None:
        logger.info("Initializing ARQ Redis pool...")  # Add logging
        _arq_redis_pool = await create_pool(redis_settings)
    return _arq_redis_pool


async def close_arq_pool():
    """
    Closes the ARQ Redis connection pool.
    Should be called during application shutdown (e.g., FastAPI lifespan).
    """
    global _arq_redis_pool
    if _arq_redis_pool:
        logger.info("Closing ARQ Redis pool...")  # Add logging
        await _arq_redis_pool.close()
        _arq_redis_pool = None


async def get_arq_pool() -> ArqRedis:
    """
    FastAPI dependency function to get the initialized ARQ Redis pool.

    Raises:
        RuntimeError: If the pool is not initialized before being requested.
                      Ensure init_arq_pool() is called at startup.

    Returns:
        The initialized ArqRedis pool instance.
    """
    if _arq_redis_pool is None:
        # This should ideally not happen if init_arq_pool is called at startup
        # Consider initializing here as a fallback, but startup is cleaner
        logger.warning("ARQ pool accessed before explicit initialization.")
        # Or raise an error:
        raise RuntimeError(
            "ARQ Redis pool has not been initialized. Call init_arq_pool() at application startup."
        )
        # await init_arq_pool() # Fallback initialization (less ideal)

    # Type checker might complain here if fallback init is used, hence the RuntimeError approach
    return _arq_redis_pool  # type: ignore


# --- Como usar no main.py (Exemplo) ---
# from fastapi import FastAPI, Depends
# from .arq_manager import get_arq_redis, close_arq_redis
# from arq.connections import ArqRedis # Import type for dependency

# app = FastAPI()

# @app.on_event("shutdown")
# async def shutdown_event():
#     await close_arq_redis()

# @app.post("/enqueue_example")
# async def enqueue_example_job(
#     message: str = "Hello ARQ",
#     arq_pool: ArqRedis = Depends(get_arq_redis) # Use the dependency
# ):
#     job = await arq_pool.enqueue_job("example_task", message) # Enqueue by function name
#     if job:
#         return {"status": "enqueued", "job_id": job.job_id}
#     else:
#         # This might happen if Redis connection fails during enqueue
#         raise HTTPException(status_code=500, detail="Failed to enqueue job")
