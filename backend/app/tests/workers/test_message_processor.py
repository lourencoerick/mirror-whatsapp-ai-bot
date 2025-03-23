import pytest
from app.workers.message_processor import MessageProcessor
from app.api.schemas.response_schema import ResponseMessage


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
        "contact_id": "5511999999999",
        "source_id": "wamid.999",
        "status": 1,
        "content_type": 1,
        "private": False,
        "provider": "evolution",
    }


@pytest.mark.unit
def test_handle_valid_message(processor, valid_message):
    response = processor.process_message(valid_message)

    assert isinstance(response, ResponseMessage)
    assert response.to == valid_message["contact_id"]
    assert response.original_message_id == valid_message["source_id"]


@pytest.mark.unit
def test_missing_required_fields_skips_processing(processor):
    incomplete_message = {
        "content": "Oi",
        "account_id": 1,
        # missing 'contact_id' and 'source_id'
    }

    result = processor.process_message(incomplete_message)
    assert result is None


@pytest.mark.unit
def test_invalid_input_type_skips_processing(processor):
    # Should simulate broken input
    result = processor.process_message(None)
    assert result is None


@pytest.mark.unit
def test_processor_response_schema(processor, valid_message):
    result = processor.process_message(valid_message)
    assert isinstance(result, ResponseMessage)
    assert result.model_dump().keys() == {
        "to",
        "original_message_id",
        "response_text",
        "provider",
        "timestamp",
    }
