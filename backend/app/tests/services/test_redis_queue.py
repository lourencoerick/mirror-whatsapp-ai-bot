import json
import pytest
from loguru import logger
from app.services.queue.redis_queue import RedisQueue
from app.config import get_settings
from redis import Redis


@pytest.fixture
def redis_queue() -> RedisQueue:
    settings = get_settings()
    redis = Redis(
        host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True
    )
    redis.flushdb()
    return RedisQueue()


@pytest.fixture
def sample_message():
    return {
        "account_id": 1,
        "content": "Test message",
        "inbox_id": 1,
        "conversation_id": 42,
        "contact_id": 10,
        "direction": "in",
    }


def test_enqueue_and_dequeue(redis_queue, sample_message):
    logger.info("[TEST] Testing enqueue → dequeue...")
    redis_queue.enqueue(sample_message)
    result = redis_queue.dequeue()

    assert result is not None
    assert result["content"] == sample_message["content"]
    assert result["conversation_id"] == sample_message["conversation_id"]
    assert redis_queue.dequeue() is None  # should now be empty


def test_queue_order(redis_queue):
    logger.info("[TEST] Testing FIFO order...")
    messages = [
        {"id": 1, "text": "first"},
        {"id": 2, "text": "second"},
        {"id": 3, "text": "third"},
    ]
    for msg in messages:
        redis_queue.enqueue(msg)

    for expected in messages:  # because lpush + brpop = FIFO
        actual = redis_queue.dequeue()
        assert actual["id"] == expected["id"]
        assert actual["text"] == expected["text"]
