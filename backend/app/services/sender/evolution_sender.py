import httpx
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.config import get_settings

settings = get_settings()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
def send_message(message: dict) -> None:
    """
    Sends a text message using the Evolution API via HTTPX.
    Retries up to 3 times in case of connection-level failures.

    Args:
        message (dict): Must contain:
            - number (str): Recipient phone number
            - text (str): Message content
    """
    try:
        payload = {
            "number": message["number"],
            "text": message["text"],
        }
        headers = {
            "apikey": settings.EVOLUTION_API_KEY,
            "Content-Type": "application/json",
        }
        url = f"https://{settings.EVOLUTION_SERVER_URL}/message/sendText/{settings.EVOLUTION_INSTANCE}"

        response = httpx.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        logger.info(
            f"[evolution_sender] Message sent successfully: {response.status_code} - {response.text}"
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            f"[evolution_sender] HTTP error: {e.response.status_code} - {e.response.text}"
        )
        raise
    except httpx.RequestError as e:
        logger.warning(f"[evolution_sender] Retriable request failure: {e}")
        raise
    except Exception as e:
        logger.exception(f"[evolution_sender] Unexpected error: {e}")
        raise
