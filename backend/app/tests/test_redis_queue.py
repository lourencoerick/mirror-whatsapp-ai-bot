from app.services.queue.redis_queue import RedisQueue


def test_redis_queue_enqueue_and_dequeue():
    queue = RedisQueue()
    message = {"text": "test", "phone_number": "123"}

    queue.enqueue(message)
    result = queue.dequeue()

    assert result == message
