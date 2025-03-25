import pytest
from app.workers.message_processor import MessageProcessor
from app.api.schemas.response import ResponseMessage


@pytest.fixture
def processor():
    return MessageProcessor()


@pytest.fixture
def valid_message():
    # return {
    #     "content": "Oi",
    #     "direction": "in",
    #     "account_id": 1,
    #     "inbox_id": 1,
    #     "conversation_id": 1,
    #     "contact_id": "5511999999999",
    #     "source_id": "wamid.999",
    #     "status": 1,
    #     "content_type": 1,
    #     "private": False,
    #     "provider": "evolution",
    # }

    return {
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


@pytest.mark.unit
def test_handle_valid_message(processor, valid_message):
    response = processor.process_message(valid_message)

    assert isinstance(response, ResponseMessage)
    assert response.to == valid_message["data"]["key"]["remoteJid"].split("@")[0]
    assert response.original_message_id == valid_message["data"]["key"]["id"]


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
