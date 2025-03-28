import asyncio
from uuid import uuid4
import json
import pytest
from unittest.mock import AsyncMock
from app.services.realtime.redis_pubsub import RedisPubSubBridge, manager_instance


# A fake PubSub class to simulate Redis pub/sub behavior.
class FakePubSub:
    def __init__(self, messages):
        # List of messages to be yielded by the listen() method.
        self.messages = messages

    async def psubscribe(self, pattern):
        # Simulate subscribing to a pattern.
        self.called_pattern = pattern

    async def listen(self):
        # Yield each message in the list.
        for message in self.messages:
            yield message


# Fixture that creates an instance of RedisPubSubBridge.
@pytest.fixture
def redis_pubsub_bridge():
    return RedisPubSubBridge()


@pytest.mark.asyncio
async def test_start_broadcasts_message(redis_pubsub_bridge, monkeypatch):
    # Create a fake pmessage with valid JSON data.
    conversation_id = uuid4()
    message = {
        "type": "pmessage",
        "channel": f"ws:conversation:{conversation_id}",
        "data": json.dumps({"text": "Hello"}),
    }
    fake_pubsub = FakePubSub([message])
    # Patch the redis.pubsub method to return our fake pubsub.
    monkeypatch.setattr(redis_pubsub_bridge.redis, "pubsub", lambda: fake_pubsub)

    # Patch manager_instance.broadcast to track its calls.
    broadcast_mock = AsyncMock()
    monkeypatch.setattr(manager_instance, "broadcast", broadcast_mock)

    # Run the start method; it will process the fake message and then exit.
    await redis_pubsub_bridge.start()

    # Verify that broadcast was called with conversation_id=1 and the correct data.
    broadcast_mock.assert_awaited_once_with(conversation_id, {"text": "Hello"})


@pytest.mark.asyncio
async def test_start_ignores_non_pmessage(redis_pubsub_bridge, monkeypatch):
    # Create a fake message that is not of type 'pmessage'.
    message = {
        "type": "subscribe",  # Non pmessage type
        "channel": "ws:conversation:1",
        "data": json.dumps({"text": "Hello"}),
    }
    fake_pubsub = FakePubSub([message])
    monkeypatch.setattr(redis_pubsub_bridge.redis, "pubsub", lambda: fake_pubsub)

    broadcast_mock = AsyncMock()
    monkeypatch.setattr(manager_instance, "broadcast", broadcast_mock)

    # Run the start method; the non-pmessage should be ignored.
    await redis_pubsub_bridge.start()

    # Verify that broadcast was not called.
    broadcast_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_handles_exception(redis_pubsub_bridge, monkeypatch):
    # Create a fake pmessage with invalid JSON data to trigger an exception.
    message = {
        "type": "pmessage",
        "channel": "ws:conversation:1",
        "data": "invalid json",
    }
    fake_pubsub = FakePubSub([message])
    monkeypatch.setattr(redis_pubsub_bridge.redis, "pubsub", lambda: fake_pubsub)

    broadcast_mock = AsyncMock()
    monkeypatch.setattr(manager_instance, "broadcast", broadcast_mock)

    # Run the start method; the exception should be caught internally.
    await redis_pubsub_bridge.start()

    # Verify that broadcast was not called since JSON parsing failed.
    broadcast_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_psubscribe_called(redis_pubsub_bridge, monkeypatch):
    # Create a fake message to ensure that psubscribe is called.
    message = {
        "type": "pmessage",
        "channel": "ws:conversation:1",
        "data": json.dumps({"text": "Test"}),
    }
    fake_pubsub = FakePubSub([message])

    # Replace the psubscribe method with a spy that saves the called pattern.
    async def fake_psubscribe(pattern):
        fake_pubsub.called_pattern = pattern

    fake_pubsub.psubscribe = fake_psubscribe

    monkeypatch.setattr(redis_pubsub_bridge.redis, "pubsub", lambda: fake_pubsub)

    broadcast_mock = AsyncMock()
    monkeypatch.setattr(manager_instance, "broadcast", broadcast_mock)

    # Run the start method; it should subscribe before processing messages.
    await redis_pubsub_bridge.start()

    # Verify that psubscribe was called with the correct pattern.
    assert getattr(fake_pubsub, "called_pattern", None) == "ws:conversation:*"
