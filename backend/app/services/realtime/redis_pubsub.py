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

    - Subscribes to patterns:
        - "ws:conversation:*"
        - "ws:account:*:conversations"
    - Parses the relevant UUID from the channel
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
        await pubsub.psubscribe(
            "ws:conversation:*", "ws:account:*:conversations", "ws:instances:*"
        )

        logger.info("[RedisPubSub] Subscribed to ws:* patterns")

        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue

            try:
                channel = message["channel"]
                data = json.loads(message["data"])
                logger.info(
                    f"[RedisPubSub] Preparing to broacasting {data} recieved in the channel {channel}"
                )

                if channel.startswith("ws:conversation:"):
                    conversation_id = UUID(channel.split(":")[-1])
                    await manager_instance.broadcast(conversation_id, data)
                elif channel.startswith("ws:instances:"):
                    instance_id = UUID(channel.split(":")[-1])
                    await manager_instance.broadcast(instance_id, data)
                elif channel.startswith("ws:account:") and channel.endswith(
                    ":conversations"
                ):
                    account_id = UUID(channel.split(":")[2])
                    await manager_instance.broadcast(account_id, data)

            except Exception as e:
                logger.warning(f"[RedisPubSub] Failed to handle message: {e}")
