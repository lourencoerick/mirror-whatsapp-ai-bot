import json
from uuid import UUID
from redis.asyncio import Redis
from loguru import logger
from app.config import get_settings

settings = get_settings()


async def publish_to_conversation_ws(conversation_id: UUID, data: dict):
    """
    Publish a message to a Redis Pub/Sub channel for WebSocket delivery.

    This allows any part of the system (FastAPI or worker) to send messages
    to clients connected to a specific conversation.

    Args:
        conversation_id (UUID): The target conversation ID.
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


async def publish_to_account_conversations_ws(account_id: UUID, data: dict):
    """
    Publish a message to update the conversation list for a given account.

    Args:
        account_id (UUID): The account whose connected clients should receive the update.
        data (dict): Payload to be sent (e.g., new conversation preview, status update).
    """
    redis = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=True,
    )
    channel = f"ws:account:{account_id}:conversations"
    await redis.publish(channel, json.dumps(data))


async def publish_to_instance_ws(instance_id: UUID, data: dict):
    redis = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=True,
    )
    channel = f"ws:instances:{instance_id}"
    logger.debug(
        f"Publising {data} of the instance : {instance_id} to the channel: {channel}"
    )
    await redis.publish(channel, json.dumps(data))
