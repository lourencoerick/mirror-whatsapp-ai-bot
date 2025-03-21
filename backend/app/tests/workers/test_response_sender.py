import pytest
from typing import Dict
from unittest.mock import MagicMock
from app.workers.response_sender import ResponseSender


@pytest.fixture
def valid_response_message() -> Dict[str, str]:
    return {"to": "5511999999999", "response_text": "Bot: Hello!"}


@pytest.fixture
def invalid_response_message() -> Dict[str, str]:
    return {"to": "", "response_text": None}  # Invalid: empty string  # Invalid: None


@pytest.fixture
def sender_with_mocked_queue() -> ResponseSender:
    sender = ResponseSender()
    sender.queue = MagicMock()
    return sender


def test_valid_message_should_pass_validation(valid_response_message: Dict[str, str]):
    """It should validate a message that has all required fields."""
    sender = ResponseSender()

    is_valid = sender.is_valid_message(valid_response_message)

    assert is_valid is True


def test_invalid_message_should_fail_validation(
    invalid_response_message: Dict[str, str],
):
    """It should fail validation if any required field is missing or empty."""
    sender = ResponseSender()

    is_valid = sender.is_valid_message(invalid_response_message)

    assert is_valid is False


def test_sender_should_call_send_to_platform_for_valid_message(
    valid_response_message: Dict[str, str], sender_with_mocked_queue: ResponseSender
):
    """It should call send_to_platform() once for a valid dequeued message."""
    sender = sender_with_mocked_queue
    sender.queue.dequeue.return_value = valid_response_message
    sender.send_to_platform = MagicMock()

    message = sender.queue.dequeue()
    if sender.is_valid_message(message):
        sender.send_to_platform(message)

    sender.send_to_platform.assert_called_once_with(valid_response_message)


def test_sender_should_not_call_send_to_platform_for_invalid_message(
    invalid_response_message: Dict[str, str], sender_with_mocked_queue: ResponseSender
):
    """It should NOT call send_to_platform() for an invalid message."""
    sender = sender_with_mocked_queue
    sender.queue.dequeue.return_value = invalid_response_message
    sender.send_to_platform = MagicMock()

    message = sender.queue.dequeue()
    if sender.is_valid_message(message):
        sender.send_to_platform(message)

    sender.send_to_platform.assert_not_called()
