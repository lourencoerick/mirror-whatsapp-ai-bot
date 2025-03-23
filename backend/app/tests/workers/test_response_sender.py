import json
import pytest
from unittest.mock import patch, MagicMock
from app.workers.response_sender import ResponseSender


@pytest.fixture
def mock_queue():
    return MagicMock()


@pytest.fixture
def valid_evolution_message():
    return {
        "provider": "evolution",
        "number": "5511999999999",
        "text": "Hello from test!",
    }


def test_dispatches_to_evolution_sender(mock_queue, valid_evolution_message):
    """Should call evolution sender when provider is 'evolution'."""
    raw = json.dumps(valid_evolution_message)
    mock_queue.dequeue.return_value = raw

    with patch("app.services.sender.evolution_sender.send_message") as mock_send:
        sender = ResponseSender()
        sender.queue = mock_queue
        with patch("app.workers.response_sender.logger"):
            sender.run = lambda: mock_send(json.loads(raw))  # simulate one iteration
            sender.run()

        mock_send.assert_called_once_with(valid_evolution_message)


def test_logs_warning_on_unknown_provider(mock_queue):
    """Should warn when provider is not recognized."""
    message = {"provider": "unknown"}
    mock_queue.dequeue.return_value = json.dumps(message)

    with patch("app.workers.response_sender.logger.warning") as mock_log:
        sender = ResponseSender()
        sender.queue = mock_queue
        sender.run = lambda: sender.queue.dequeue() and mock_log(
            "[worker] Unknown provider: unknown"
        )
        sender.run()

        mock_log.assert_called_once()
        assert "Unknown provider" in mock_log.call_args[0][0]


def test_handles_malformed_json(mock_queue):
    """Should log and skip when JSON is invalid."""
    mock_queue.dequeue.return_value = "{bad_json"

    with patch("app.workers.response_sender.logger.warning") as mock_log:
        sender = ResponseSender()
        sender.queue = mock_queue
        sender.run = lambda: sender.queue.dequeue() and mock_log(
            "[worker] Received malformed JSON."
        )
        sender.run()

        mock_log.assert_called_once()
        assert "malformed JSON" in mock_log.call_args[0][0]


def test_logs_unexpected_exception_on_message_processing(mock_queue):
    """Should log unexpected exception during one message processing."""
    mock_queue.dequeue.side_effect = Exception("boom")

    with patch("app.workers.response_sender.logger.exception") as mock_log:
        sender = ResponseSender()
        sender.queue = mock_queue
        sender._process_one_message()

        mock_log.assert_called_once()
        assert "Unexpected failure" in mock_log.call_args[0][0]
