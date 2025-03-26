import pytest
from unittest.mock import patch, MagicMock
from httpx import RequestError, HTTPStatusError, Response
from app.services.sender import evolution as evolution_sender
from app.models.message import Message


@pytest.fixture
def mock_message():
    contact = MagicMock()
    contact.phone_number = "5511999999999"

    message = MagicMock(spec=Message)
    message.contact = contact
    message.content = "Test message"
    return message


@pytest.mark.unit
def test_send_message_success(mock_message):
    """Should send message successfully and return parsed JSON."""
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock(status_code=200, text="OK")
        mock_response.json.return_value = {"id": "abc123", "status": "SENT"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = evolution_sender.send_message(mock_message)

        mock_post.assert_called_once()
        assert result == {"id": "abc123", "status": "SENT"}
        mock_response.raise_for_status.assert_called_once()


@pytest.mark.unit
def test_send_message_http_error_logged(mock_message):
    """Should raise and log HTTP error if status is 4xx/5xx."""
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            message="Bad Request",
            request=MagicMock(),
            response=MagicMock(status_code=400),
        )
        mock_post.return_value = mock_response

        with patch("app.services.sender.evolution.logger.error") as mock_log:
            with pytest.raises(HTTPStatusError):
                evolution_sender.send_message(mock_message)
            mock_log.assert_called()
            assert "HTTP error" in mock_log.call_args[0][0]


@pytest.mark.unit
def test_send_message_retry_on_request_error(mock_message):
    """Should retry 3 times on connection-level failure."""
    with patch("httpx.post", side_effect=RequestError("Connection error")) as mock_post:
        with pytest.raises(RequestError):
            evolution_sender.send_message(mock_message)

        assert mock_post.call_count == 3


@pytest.mark.unit
def test_send_message_unexpected_exception(mock_message):
    """Should catch and log unexpected exception."""
    with patch("httpx.post", side_effect=ValueError("unexpected error")):
        with patch("app.services.sender.evolution.logger.exception") as mock_log:
            with pytest.raises(ValueError):
                evolution_sender.send_message(mock_message)
            mock_log.assert_called()
            assert "Unexpected error" in mock_log.call_args[0][0]
