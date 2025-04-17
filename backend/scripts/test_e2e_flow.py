import pytest
import time
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services.queue.redis_queue import RedisQueue
from workers.consumer.message_consumer import MessageConsumer
from app.workers.message_processor import MessageProcessor
from workers.response_sender.response_sender import ResponseSender
from app.api.schemas.response import ResponseMessage
from app.services.sender import evolution as evolution_sender
from app.database import SessionLocal

client = TestClient(app)


@pytest.mark.integration
def test_end_to_end_evolution_flow(monkeypatch):
    # Step 0: Mocks
    mock_sent = []

    db = SessionLocal()

    def fake_send(message: ResponseMessage):
        mock_sent.append(message)
        return True

    monkeypatch.setattr(evolution_sender, "send_message", fake_send)

    # Clean all queues
    RedisQueue("message_queue").clear()
    RedisQueue("ready_for_processing_queue").clear()
    RedisQueue("response_queue").clear()

    # Step 1: Send webhook payload
    payload = {
        "event": "messages.upsert",
        "sender": "5511935032393@s.whatsapp.net",
        "data": {
            "instanceId": "test-instance",
            "messageType": "chat",
            "messageTimestamp": 1711234567,
            "key": {
                "id": "msg-001",
                "remoteJid": "5511912345678@s.whatsapp.net",
                "fromMe": False,
            },
            "message": {"conversation": "Olá, esse é um teste E2E!"},
        },
    }

    response = client.post("/webhook/evolution_whatsapp", json=payload)
    assert response.status_code == 202
    assert response.json()["status"] == "message enqueued"

    # Step 2: Consume → DB + enqueue to ready_for_processing
    consumer = MessageConsumer()
    raw = consumer.input_queue.dequeue()

    consumer._handle_message(db, raw)
    consumer.output_queue.enqueue(payload)

    # Step 3: Processor → response_queue
    processor = MessageProcessor()
    raw2 = processor.input_queue.dequeue()
    response_msg = processor.process_message(raw2)
    assert isinstance(response_msg, ResponseMessage)
    processor.output_queue.enqueue(response_msg.model_dump_json())

    # Step 4: ResponseSender → external service (mocked)
    sender = ResponseSender()
    raw3 = sender.queue.dequeue()
    parsed = ResponseMessage.model_validate_json(raw3)
    evolution_sender.send_message(parsed)

    # # Final checks
    assert len(mock_sent) == 1
    assert mock_sent[0].to == "5511912345678"
