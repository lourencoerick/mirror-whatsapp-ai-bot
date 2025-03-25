import pytest
from unittest.mock import patch, MagicMock
from httpx import RequestError, HTTPStatusError, Response
from app.services.sender import evolution as evolution_sender


@pytest.fixture
def valid_message():
    return {
        "number": "5511999999999",
        "text": "Test message",
    }


@pytest.mark.unit
def test_send_message_success(valid_message):
    """Should send message successfully and log info."""
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock(status_code=200, text="OK")
        mock_post.return_value = mock_response

        evolution_sender.send_message(valid_message)

        mock_post.assert_called_once()
        assert mock_response.raise_for_status.called


@pytest.mark.unit
def test_send_message_http_error_logged(valid_message):
    """Should raise and log HTTP error if status is 4xx/5xx."""
    with patch("httpx.post") as mock_post:
        request = MagicMock()
        response = Response(status_code=400, request=request)
        mock_post.return_value = response

        with patch.object(
            Response,
            "raise_for_status",
            side_effect=HTTPStatusError(
                "Bad Request", request=request, response=response
            ),
        ):
            with patch("app.services.sender.evolution.logger.error") as mock_log:
                with pytest.raises(HTTPStatusError):
                    evolution_sender.send_message(valid_message)
                mock_log.assert_called()
                assert "HTTP error" in mock_log.call_args[0][0]


@pytest.mark.unit
def test_send_message_retry_on_request_error(valid_message):
    """Should retry 3 times on connection-level failure."""
    with patch("httpx.post", side_effect=RequestError("Connection error")) as mock_post:
        with pytest.raises(RequestError):
            evolution_sender.send_message(valid_message)

        assert mock_post.call_count == 3


@pytest.mark.unit
def test_send_message_unexpected_exception(valid_message):
    """Should catch and log unexpected exception."""
    with patch("httpx.post", side_effect=ValueError("unexpected error")):
        with patch("app.services.sender.evolution.logger.exception") as mock_log:
            with pytest.raises(ValueError):
                evolution_sender.send_message(valid_message)
            mock_log.assert_called()
            assert "Unexpected error" in mock_log.call_args[0][0]
