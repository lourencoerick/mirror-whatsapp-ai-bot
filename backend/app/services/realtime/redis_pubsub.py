import json
from uuid import UUID
from redis.asyncio import Redis
from loguru import logger
from app.services.realtime.ws_manager import manager_instance
from app.config import get_settings

settings = get_settings()


class RedisPubSubBridge:
    """
    Redis Pub/Sub bridge for broadcasting WebSocket messages across processes.

    - Subscribes to pattern "ws:conversation:*"
    - Listens for new messages on Redis channels
    - Parses the conversation_id from the channel
    - Forwards the message to the correct clients via WebSocketManager

    This ensures distributed systems (e.g. FastAPI + workers) can all trigger real-time WebSocket delivery.
    """

    def __init__(self):
        self.redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=0,
            decode_responses=True,
        )

    async def start(self):
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("ws:conversation:*")

        logger.info("[RedisPubSub] Subscribed to ws:conversation:*")

        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue

            try:
                channel = message["channel"]
                conversation_id = UUID(channel.split(":")[-1])
                data = json.loads(message["data"])

                await manager_instance.broadcast(conversation_id, data)

            except Exception as e:
                logger.warning(f"[RedisPubSub] Failed to handle message: {e}")
