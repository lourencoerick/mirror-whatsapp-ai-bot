import redis
import json
import os
from app.services.queue.iqueue import IQueue


class RedisQueue(IQueue):
    """Redis-backed implementation of IQueue."""

    def __init__(self, queue_name="message_queue"):
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        self.client = redis.Redis(host=host, port=port, db=0)
        self.queue_name = queue_name

    def enqueue(self, message: dict) -> None:
        """Push a message onto the queue."""
        self.client.lpush(self.queue_name, json.dumps(message))

    def dequeue(self) -> dict:
        """Pop a message from the queue."""
        _, raw = self.client.brpop(self.queue_name)
        return json.loads(raw)
