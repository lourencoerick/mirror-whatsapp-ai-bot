import redis
import json
from app.services.queue.iqueue import IQueue


class RedisQueue(IQueue):
    """Redis-backed implementation of IQueue."""

    def __init__(self, host="localhost", port=6379, db=0, queue_name="message_queue"):
        self.client = redis.Redis(host=host, port=port, db=db)
        self.queue_name = queue_name

    def enqueue(self, message: dict) -> None:
        """Push a message onto the queue."""
        self.client.lpush(self.queue_name, json.dumps(message))

    def dequeue(self) -> dict:
        """Pop a message from the queue."""
        _, raw = self.client.brpop(self.queue_name)
        return json.loads(raw)
