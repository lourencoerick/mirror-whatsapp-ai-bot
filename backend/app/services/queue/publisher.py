from app.services.queue.redis_queue import RedisQueue


def publish_message_to_queue(message_id: int, queue_name="response_queue"):
    queue = RedisQueue(queue_name=queue_name)
    queue.enqueue({"message_id": message_id})
