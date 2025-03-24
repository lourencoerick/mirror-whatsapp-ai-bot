import pytest
from app.services.parser.evolution_parser import parse_evolution_message


@pytest.mark.unit
def test_parse_valid_evolution_payload():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {
                "remoteJid": "5511941986775@s.whatsapp.net",
                "fromMe": True,
                "id": "wamid.12345",
            },
            "pushName": "LL",
            "message": {"conversation": "Oi, tudo bem?"},
            "messageType": "conversation",
            "messageTimestamp": 1742607528,
        },
    }

    result = parse_evolution_message(payload)

    assert isinstance(result, dict)
    assert result["content"] == "Oi, tudo bem?"
    assert result["direction"] == "out"
    assert result["source_id"] == "wamid.12345"
    assert result["content_attributes"]["provider"] == "evolution"


@pytest.mark.unit
def test_parse_evolution_payload_without_message():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"id": "xyz"},
            # 'message' field is missing
        },
    }

    result = parse_evolution_message(payload)
    assert result is None


@pytest.mark.unit
def test_parse_invalid_payload_format():
    payload = {"not": "valid"}

    result = parse_evolution_message(payload)
    assert result is None
