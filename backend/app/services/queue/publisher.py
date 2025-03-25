# app/queue/publisher.py

import json
from redis import Redis
from loguru import logger
from typing import Any
from app.config import get_settings

settings = get_settings()


# Singleton Redis client
redis_client = Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
)


def publish_to_queue(channel: str, payload: Any) -> bool:
    """
    Publishes a message to the specified Redis channel/queue.

    Args:
        channel (str): Redis list key (e.g., 'incoming_messages').
        payload (Any): Serializable content (typically a dict).

    Returns:
        bool: Whether the message was successfully queued.
    """
    try:
        message = json.dumps(payload)
        redis_client.rpush(channel, message)
        logger.debug(f"[publisher] Enqueued to '{channel}': {payload}")
        return True
    except Exception as e:
        logger.exception(f"[publisher] Failed to publish to queue: {e}")
        return False
