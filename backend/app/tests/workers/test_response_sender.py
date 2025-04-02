import pytest
from unittest.mock import patch, MagicMock
from app.workers.response_sender import ResponseSender


@pytest.fixture
def mock_queue() -> MagicMock:
    return MagicMock()


@pytest.fixture
def valid_payload() -> dict:
    return {"message_id": 123}


@pytest.fixture
def mock_message() -> MagicMock:
    message = MagicMock()
    message.id = 123
    message.content = "Olá"
    return message


# with patch("app.workers.response_sender.evolution_send_message") as mock_send:
#     ..
@pytest.mark.unit
def test_processes_valid_message_successfully(mock_queue, valid_payload, mock_message):
    """
    Should process a valid message ID, send it via evolution,
    and update its status and source_id.
    """
    mock_queue.dequeue.return_value = valid_payload

    with patch(
        "app.services.repository.message.find_message_by_id", return_value=mock_message
    ), patch(
        "app.workers.response_sender.evolution_send_message",
        return_value={"status": "SENT", "key": {"id": "external-abc"}},
    ):
        sender = ResponseSender()
        sender.queue = mock_queue
        sender._process_one_message()

        assert mock_message.status == "sent"
        assert mock_message.source_id == "external-abc"


@pytest.mark.unit
def test_logs_warning_when_message_not_found(mock_queue, valid_payload):
    """
    Should log a warning if the message is not found in the database.
    """
    mock_queue.dequeue.return_value = valid_payload

    with patch(
        "app.services.repository.message.find_message_by_id", return_value=None
    ), patch("app.workers.response_sender.logger.warning") as mock_log:
        sender = ResponseSender()
        sender.queue = mock_queue
        sender._process_one_message()

        mock_log.assert_called_once()
        assert "not found" in mock_log.call_args[0][0]


@pytest.mark.unit
def test_logs_error_when_missing_message_id(mock_queue):
    """
    Should log a warning if the 'message_id' field is missing from the payload.
    """
    mock_queue.dequeue.return_value = {"unexpected": True}

    with patch("app.workers.response_sender.logger.warning") as mock_log:
        sender = ResponseSender()
        sender.queue = mock_queue
        sender._process_one_message()

        mock_log.assert_called_once()
        assert "missing 'message_id'" in mock_log.call_args[0][0]


@pytest.mark.unit
def test_logs_unexpected_exception(mock_queue):
    """
    Should catch and log any unexpected exceptions during processing.
    """
    mock_queue.dequeue.side_effect = Exception("boom")

    with patch("app.workers.response_sender.logger.exception") as mock_log:
        sender = ResponseSender()
        sender.queue = mock_queue
        sender._process_one_message()

        mock_log.assert_called_once()
        assert "Unexpected failure" in mock_log.call_args[0][0]
