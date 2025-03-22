import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.tests.utils.setup_test_data import setup_test_data


client = TestClient(app)


@pytest.fixture
def valid_message_payload():
    return {
        "content": "Olá, tudo bem?",
        "direction": "in",
        "account_id": 1,
        "inbox_id": 1,
        "conversation_id": 1,
        "contact_id": 1,
        "user_id": None,
        "source_id": "wamid.1234567890",
        "status": 1,
        "content_type": 1,
        "content_attributes": {"source": "whatsapp"},
        "private": False,
    }


def test_create_message_success(valid_message_payload):
    response = client.post("/messages", json=valid_message_payload)

    db = SessionLocal()
    setup_test_data(db)

    assert response.status_code == 201
    response_data = response.json()
    assert "message_id" in response_data
    assert isinstance(response_data["message_id"], int)


def test_create_message_without_optional_fields():
    minimal_payload = {
        "content": "Olá!",
        "direction": "out",
        "account_id": 1,
        "inbox_id": 1,
        "conversation_id": 1,
        "private": False,
        "content_type": 1,
    }

    response = client.post("/messages", json=minimal_payload)

    assert response.status_code == 201
    assert "message_id" in response.json()


def test_create_message_with_invalid_direction(valid_message_payload):
    invalid_payload = valid_message_payload.copy()
    invalid_payload["direction"] = "invalid"

    response = client.post("/messages", json=invalid_payload)

    assert response.status_code == 422  # Pydantic validation error
    assert "detail" in response.json()
