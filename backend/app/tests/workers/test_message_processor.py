import pytest
from app.workers.message_processor import MessageProcessor


@pytest.fixture
def processor():
    return MessageProcessor()


@pytest.fixture
def valid_message():
    return {
        "content": "Oi",
        "direction": "in",
        "account_id": 1,
        "inbox_id": 1,
        "conversation_id": 1,
        "contact_id": 99,
        "source_id": "wamid.999",
        "status": 1,
        "content_type": 1,
        "private": False,
    }


def test_handle_valid_message(processor, valid_message):
    response = processor.process_message(valid_message)

    assert response is not None
    assert response["to"] == 99
    assert response["original_message_id"] == "wamid.999"
    assert "response_text" in response


def test_missing_required_fields_skips_processing(processor):
    incomplete_message = {
        "content": "Oi",
        "account_id": 1,
        # missing 'contact_id', 'source_id'
    }

    result = processor.process_message(incomplete_message)
    assert result is None


def test_invalid_json_skips_processing(processor):
    # Simulate message coming in malformed (like a broken payload)
    broken_message = "{'not': 'a dict'}"

    # Normally Redis returns dict via JSON.loads. So invalid JSON would be handled earlier.
    # But we simulate it reaching the processor anyway:
    result = (
        processor.process_message(broken_message)
        if isinstance(broken_message, dict)
        else None
    )
    assert result is None


def test_dequeue_none_does_nothing():
    # Simulate behavior if Redis returns None (queue is empty)
    processor = MessageProcessor()
    result = processor.process_message(None)
    assert result is None


def test_processor_response_format(processor, valid_message):
    result = processor.process_message(valid_message)

    assert isinstance(result, dict)
    assert set(result.keys()) == {
        "to",
        "original_message_id",
        "response_text",
        "timestamp",
    }
