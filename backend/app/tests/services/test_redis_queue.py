import json
import pytest
from unittest.mock import MagicMock
from app.services.queue.redis_queue import RedisQueue


@pytest.fixture
def fake_redis():
    # Create a fake Redis object to simulate Redis with an internal queue
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

    # Optionally, simulate flushdb if needed
    fake.flushdb.side_effect = lambda: fake.queue.clear()

    return fake


@pytest.fixture
def redis_queue(fake_redis):
    # Create an instance of RedisQueue and inject fake_redis
    queue = RedisQueue()
    queue.redis = fake_redis
    return queue


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


@pytest.mark.unit
def test_queue_order(redis_queue):
    messages = [
        {"id": 1, "text": "first"},
        {"id": 2, "text": "second"},
        {"id": 3, "text": "third"},
    ]
    for msg in messages:
        redis_queue.enqueue(msg)

    # Check if the dequeue order is FIFO
    for expected in messages:
        actual = redis_queue.dequeue()
        assert actual["id"] == expected["id"]
        assert actual["text"] == expected["text"]
