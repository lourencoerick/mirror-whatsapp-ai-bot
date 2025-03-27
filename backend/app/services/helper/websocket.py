import json
from redis.asyncio import Redis
from app.config import get_settings

settings = get_settings()


async def publish_to_conversation_ws(conversation_id: int, data: dict):
    """
    Publish a message to a Redis Pub/Sub channel for WebSocket delivery.

    This allows any part of the system (FastAPI or worker) to send messages
    to clients connected to a specific conversation.

    Args:
        conversation_id (int): The target conversation ID.
        data (dict): The message payload to be delivered over WebSocket.
    """
    redis = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=True,
    )
    channel = f"ws:conversation:{conversation_id}"
    await redis.publish(channel, json.dumps(data))
