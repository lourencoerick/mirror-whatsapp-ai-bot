import redis
import json
import os
from loguru import logger
from dotenv import load_dotenv

from app.services.queue.iqueue import IQueue


load_dotenv()


class RedisQueue(IQueue):
    """Redis-backed implementation of IQueue."""

    def __init__(self, queue_name: str = "message_queue"):
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        self.client = redis.Redis(host=host, port=port, db=db)
        self.queue_name = queue_name
        logger.info(f"Connected to Redis at {host}:{port} (db={db})")

    def enqueue(self, message: dict) -> None:
        """Push a message onto the queue."""
        self.client.lpush(self.queue_name, json.dumps(message))
        logger.debug(f"[enqueue] Message enqueued: {message}")

    def dequeue(self) -> dict:
        """Pop a message from the queue."""
        _, raw = self.client.brpop(self.queue_name)
        message = json.loads(raw)
        logger.debug(f"[dequeue] Message dequeued: {message}")
        return message
