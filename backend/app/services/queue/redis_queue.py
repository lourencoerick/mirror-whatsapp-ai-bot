import json
import datetime
from redis import Redis
from typing import Optional
from loguru import logger
from app.config import get_settings
from app.services.queue.iqueue import IQueue
from app.config import get_settings

settings = get_settings()


def default_converter(o):
    if isinstance(o, datetime.datetime):
        return o.isoformat()
    raise TypeError(f"The type {type(o)} is not serializable")


class RedisQueue(IQueue):
    """
    Redis-backed message queue for async processing.

    Uses a simple list-based queue with JSON serialization.
    """

    def __init__(self, queue_name: str = "messages"):
        self.queue_name = queue_name
        self.client = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True,
        )
        logger.debug(
            f"[RedisQueue] Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}"
        )

    def enqueue(self, message: dict) -> None:
        """Push a message to the Redis queue."""
        serialized = json.dumps(message, default=default_converter)
        self.client.lpush(self.queue_name, serialized)
        logger.debug(f"[RedisQueue] Enqueued message: {serialized}")

    def dequeue(self) -> Optional[dict]:
        """Pop a message from the queue (FIFO)."""
        result = self.client.brpop(self.queue_name, timeout=1)
        if result is None:
            logger.debug("[RedisQueue] Queue is empty.")
            return None

        _, raw = result
        try:
            deserialized = json.loads(raw)
            logger.debug(f"[RedisQueue] Dequeued message: {deserialized}")
            return deserialized
        except json.JSONDecodeError as e:
            logger.error(
                f"[RedisQueue] Failed to deserialize message: {raw} | Error: {e}"
            )
            return None

    def clear(self):
        """
        Clear all items from the queue.
        """
        self.client.delete(self.queue_name)
