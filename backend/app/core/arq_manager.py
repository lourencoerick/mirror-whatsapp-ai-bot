import redis.asyncio as redis
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from typing import Optional
from loguru import logger


from app.workers.batch.contacts.contact_creator import (
    redis_settings,
)


_arq_redis_pool: Optional[ArqRedis] = None


async def init_arq_pool() -> ArqRedis:
    global _arq_redis_pool
    if _arq_redis_pool is None:
        logger.info("Initializing ARQ Redis pool...")
        logger.debug(f"Using Redis Settings for ARQ Pool: {redis_settings}")
        try:
            pool_instance = await create_pool(redis_settings)
            logger.debug(
                f"create_pool returned: {pool_instance}, type: {type(pool_instance)}"
            )
            _arq_redis_pool = pool_instance
            logger.info("ARQ Redis pool initialized and stored globally.")
        except Exception as e:
            logger.exception(f"Failed during ARQ pool creation: {e}")
            raise
    else:
        logger.warning("ARQ pool initialization skipped (already initialized).")

    return _arq_redis_pool


async def close_arq_pool():
    global _arq_redis_pool
    if _arq_redis_pool:
        logger.info("Closing ARQ Redis pool...")
        await _arq_redis_pool.close()
        _arq_redis_pool = None
        logger.info("ARQ pool closed.")
    else:
        logger.warning("Attempted to close ARQ pool, but it was not initialized.")


def get_arq_pool() -> ArqRedis:
    if _arq_redis_pool is None:
        logger.error("ARQ pool accessed before initialization or after closure!")
        raise RuntimeError(
            "ARQ Redis pool has not been initialized. Call init_arq_pool() at application startup."
        )
    logger.debug(
        f"get_arq_pool returning object: {_arq_redis_pool}, type: {type(_arq_redis_pool)}"
    )
    return _arq_redis_pool
