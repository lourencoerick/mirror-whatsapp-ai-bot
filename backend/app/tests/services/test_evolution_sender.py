import pytest
from unittest.mock import patch, MagicMock
from httpx import RequestError, HTTPStatusError, Response
from app.services.sender import evolution as evolution_sender
from app.models.message import Message
from app.models.inbox import Inbox


@pytest.fixture
def mock_message():
    """Creates a mock Message object."""
    contact = MagicMock()
    contact.phone_number = "5511999999999"

    message = MagicMock(spec=Message)
    message.contact = contact
    message.content = "Test message"
    return message


@pytest.fixture
def mock_inbox():
    """Creates a mock Inbox object."""
    inbox = MagicMock(spec=Inbox)
    inbox.channel_details = {
        "id": "test_channel_id",
        "logical_token_encrypted": "encrypted_token",
    }
    return inbox


@pytest.mark.unit
def test_send_message_success(mock_message, mock_inbox):
    """Should send message successfully and return parsed JSON."""
    with patch("httpx.post") as mock_post, patch(
        "app.services.sender.evolution.decrypt_logical_token"
    ) as mock_decrypt:
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"id": "abc123", "status": "SENT"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        mock_decrypt.return_value = "decrypted_token"

        result = evolution_sender.send_message(mock_message, mock_inbox)

        mock_post.assert_called_once()
        assert result == {"id": "abc123", "status": "SENT"}
        mock_response.raise_for_status.assert_called_once()
        mock_decrypt.assert_called_once_with("encrypted_token")


@pytest.mark.unit
def test_send_message_http_error_logged(mock_message, mock_inbox):
    """Should raise and log HTTP error if status is 4xx/5xx."""
    with patch("httpx.post") as mock_post, patch(
        "app.services.sender.evolution.decrypt_logical_token"
    ) as mock_decrypt:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPStatusError(
            message="Bad Request",
            request=MagicMock(),
            response=MagicMock(status_code=400),
        )
        mock_post.return_value = mock_response
        mock_decrypt.return_value = "decrypted_token"

        with patch("app.services.sender.evolution.logger.error") as mock_log:
            with pytest.raises(HTTPStatusError):
                evolution_sender.send_message(mock_message, mock_inbox)
            mock_log.assert_called()
            assert "HTTP error" in mock_log.call_args[0][0]
        mock_decrypt.assert_called_once_with("encrypted_token")


@pytest.mark.unit
def test_send_message_retry_on_request_error(mock_message, mock_inbox):
    """Should retry 3 times on connection-level failure."""
    with patch(
        "httpx.post", side_effect=RequestError("Connection error")
    ) as mock_post, patch(
        "app.services.sender.evolution.decrypt_logical_token"
    ) as mock_decrypt:
        mock_decrypt.return_value = "decrypted_token"
        with pytest.raises(RequestError):
            evolution_sender.send_message(mock_message, mock_inbox)

        assert mock_post.call_count == 3
        mock_decrypt.assert_called()


@pytest.mark.unit
def test_send_message_unexpected_exception(mock_message, mock_inbox):
    """Should catch and log unexpected exception."""
    with patch("httpx.post", side_effect=ValueError("unexpected error")), patch(
        "app.services.sender.evolution.logger.exception"
    ) as mock_log, patch(
        "app.services.sender.evolution.decrypt_logical_token"
    ) as mock_decrypt:
        mock_decrypt.return_value = "decrypted_token"
        with pytest.raises(ValueError):
            evolution_sender.send_message(mock_message, mock_inbox)
        mock_log.assert_called()
        assert "Unexpected error" in mock_log.call_args[0][0]
        mock_decrypt.assert_called()
