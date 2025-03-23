import json
import pytest
from unittest.mock import MagicMock
from app.services.queue.redis_queue import RedisQueue


# Fixture to create a fake Redis object with an internal queue
@pytest.fixture
def fake_redis():
    fake = MagicMock()
    fake.queue = []

    # Simulate the behavior of lpush (inserts at the beginning of the list)
    def lpush(queue_name, item):
        fake.queue.insert(0, item)

    fake.lpush.side_effect = lpush

    # Simulate the behavior of brpop (removes from the end of the list, ensuring FIFO)
    def brpop(queue_name, timeout=0):
        if fake.queue:
            return (queue_name, fake.queue.pop())
        return None

    fake.brpop.side_effect = brpop

    # Optionally, simulate flushdb to clear the queue
    fake.flushdb.side_effect = lambda: fake.queue.clear()

    return fake


# Fixture to create an instance of RedisQueue with fake Redis injected.
# We use monkeypatch to override the Redis class in the module.
@pytest.fixture
def redis_queue(monkeypatch, fake_redis):
    # Patch the Redis class in the module so that any call to Redis(...) returns fake_redis
    monkeypatch.setattr(
        "app.services.queue.redis_queue.Redis", lambda *args, **kwargs: fake_redis
    )
    # Now, when we instantiate RedisQueue, it won't try to connect to um servidor real.
    queue = RedisQueue()
    return queue


# Unit test for enqueue and dequeue functionality
@pytest.mark.unit
def test_enqueue_and_dequeue(redis_queue):
    message = {
        "account_id": 1,
        "content": "Test message",
        "inbox_id": 1,
        "conversation_id": 42,
        "contact_id": 10,
        "direction": "in",
    }
    redis_queue.enqueue(message)
    result = redis_queue.dequeue()

    assert result is not None
    assert result["content"] == message["content"]
    assert result["conversation_id"] == message["conversation_id"]
    # After dequeuing the only item, the queue should be empty
    assert redis_queue.dequeue() is None


# Unit test to ensure FIFO order of the queue
@pytest.mark.unit
def test_queue_order(redis_queue):
    messages = [
        {"id": 1, "text": "first"},
        {"id": 2, "text": "second"},
        {"id": 3, "text": "third"},
    ]
    for msg in messages:
        redis_queue.enqueue(msg)

    # Check that the dequeue order is FIFO
    for expected in messages:
        actual = redis_queue.dequeue()
        assert actual["id"] == expected["id"]
        assert actual["text"] == expected["text"]
