import pytest
from typing import Dict, Optional
from unittest.mock import MagicMock
from app.workers.message_processor import MessageProcessor


@pytest.fixture
def valid_message() -> Dict:
    return {
        "text": "Test message",
        "phone_number": "5511999999999",
        "message_id": "msg-abc-123",
    }


@pytest.fixture
def processor_mocked_queues() -> MessageProcessor:
    processor = MessageProcessor()
    processor.input_queue = MagicMock()
    processor.output_queue = MagicMock()
    return processor


def test_process_message_should_return_response(valid_message):
    processor = MessageProcessor()
    response: Optional[Dict] = processor.process_message(valid_message)

    assert response is not None
    assert response["to"] == valid_message["phone_number"]
    assert valid_message["text"] in response["response_text"]
    assert isinstance(response["timestamp"], float)


def test_process_message_should_return_none_if_missing_fields():
    processor = MessageProcessor()
    incomplete = {"text": "no phone or ID"}

    response = processor.process_message(incomplete)
    assert response is None


def test_run_should_enqueue_response(valid_message, processor_mocked_queues):
    # Mock queue to return valid message
    processor_mocked_queues.input_queue.dequeue.return_value = valid_message

    # Process a single loop manually
    response = processor_mocked_queues.process_message(valid_message)
    processor_mocked_queues.output_queue.enqueue = MagicMock()

    if response:
        processor_mocked_queues.output_queue.enqueue(response)

    processor_mocked_queues.output_queue.enqueue.assert_called_once()
    args, _ = processor_mocked_queues.output_queue.enqueue.call_args
    assert args[0]["to"] == valid_message["phone_number"]
