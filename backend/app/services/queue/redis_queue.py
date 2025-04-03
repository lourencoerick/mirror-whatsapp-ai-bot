import json
from uuid import UUID
import datetime
import asyncio
import redis.asyncio as redis
from typing import Optional
from loguru import logger

from app.config import get_settings
from app.services.queue.iqueue import IQueue

settings = get_settings()


def default_converter(o):
    """
    Convert UUID and datetime to string
    """
    if isinstance(o, datetime.datetime):
        return o.isoformat()
    if isinstance(o, UUID):
        return str(o)
    raise TypeError(f"The type {type(o)} is not serializable")


class RedisQueue(IQueue):
    """
    Redis-backed message queue for async processing using redis.asyncio.
    """

    def __init__(self, queue_name: str = "messages"):
        self.queue_name = queue_name
        self.redis: Optional[redis.Redis] = None
        self.is_connected = False
        logger.debug(
            f"[RedisQueue] Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}"
        )

    async def connect(self):
        """
        Establish connection with Redis.
        """
        try:
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=0,
                decode_responses=True,
            )
            await self.redis.ping()
            self.is_connected = True
            logger.info(
                f"[RedisQueue] Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}"
            )
        except Exception as e:
            self.is_connected = False
            logger.error(
                f"[RedisQueue] Failed to connect to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT} - {e}"
            )

    async def reconnect(self, delay=5):
        """
        Attempt to reconnect to Redis after a failure.
        """
        logger.warning(
            f"[RedisQueue] Attempting to reconnect to Redis in {delay} seconds..."
        )
        await asyncio.sleep(delay)
        await self.connect()

    async def enqueue(self, message: dict) -> None:
        """Push a message to the Redis queue."""
        if not self.is_connected or self.redis is None:
            logger.warning(
                "[RedisQueue] Not connected to Redis. Attempting to connect."
            )
            await self.connect()
            if not self.is_connected:
                logger.error("[RedisQueue] Failed to connect, enqueue aborted.")
                return

        serialized = json.dumps(message, default=default_converter)
        try:
            await self.redis.lpush(self.queue_name, serialized)
            logger.debug(f"[RedisQueue] Enqueued message: {serialized}")
        except redis.exceptions.ConnectionError as e:
            self.is_connected = False
            logger.error(f"[RedisQueue] Connection error during enqueue: {e}")

            await self.reconnect()
            if not self.is_connected:
                logger.error("[RedisQueue] Failed to reconnect, enqueue aborted.")
                return

    async def dequeue(self) -> Optional[dict]:
        """Pop a message from the queue (FIFO) using BLPOP with a timeout."""
        if not self.is_connected or self.redis is None:
            logger.warning(
                "[RedisQueue] Not connected to Redis. Attempting to connect."
            )
            await self.connect()
            if not self.is_connected:
                logger.error("[RedisQueue] Failed to connect, dequeue aborted.")
                return None

        try:
            result = await self.redis.blpop(self.queue_name, timeout=1)  # Use BLPOP
            if result is None:
                logger.debug("[RedisQueue] Queue is empty.")
                return None

            _, raw = result
            deserialized = json.loads(raw)
            logger.debug(f"[RedisQueue] Dequeued message: {deserialized}")
            return deserialized
        except json.JSONDecodeError as e:
            logger.error(
                f"[RedisQueue] Failed to deserialize message: {raw} | Error: {e}"
            )
            return None
        except redis.exceptions.ConnectionError as e:
            self.is_connected = False
            logger.error(f"[RedisQueue] Connection error during dequeue: {e}")
            await self.reconnect()
            if not self.is_connected:
                logger.error("[RedisQueue] Failed to reconnect, dequeue aborted.")
                return None
        except Exception as e:
            logger.error(f"[RedisQueue] An unexpected error occurred: {e}")
            return None

    async def clear(self):
        """Clear all items from the queue."""
        if not self.is_connected or self.redis is None:
            logger.warning("[RedisQueue] Not connected to Redis. Clear queue failed.")
            await self.connect()
            if not self.is_connected:
                logger.error("[RedisQueue] Failed to connect, clear aborted.")
                return

        try:
            await self.redis.delete(self.queue_name)
            logger.info(f"[RedisQueue] Queue '{self.queue_name}' cleared.")
        except redis.exceptions.ConnectionError as e:
            self.is_connected = False
            logger.error(f"[RedisQueue] Connection error during clear: {e}")
            await self.reconnect()

    async def close(self):
        """
        Properly close the connection.
        """
        if self.redis:
            await self.redis.close()

            await self.redis.connection_pool.disconnect()
        self.is_connected = False
        logger.info("[RedisQueue] Connection to Redis closed.")
