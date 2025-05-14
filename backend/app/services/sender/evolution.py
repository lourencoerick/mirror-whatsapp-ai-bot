import asyncio
import httpx
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from app.config import get_settings
from app.models.channels.evolution_instance import EvolutionInstance
from app.core.security import decrypt_logical_token

settings = get_settings()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def send_message(
    message_content: str, phone_number: str, evolution_instance: EvolutionInstance
) -> dict:
    """
    Sends a text message using the Evolution API via HTTPX.
    Retries up to 3 times in case of connection-level failures.

    Args:
        message (Message): Must contain:
            - number (str): Recipient phone number
            - text (str): Message content
        evolution_instance (EvolutionInstance): evolution_instance to send message from
    """
    try:
        logger.debug(f"Evolution Instance: {evolution_instance}")
        instance_id = evolution_instance.id
        api_key = decrypt_logical_token(evolution_instance.logical_token_encrypted)

        payload = {
            "number": phone_number,
            "text": message_content,
        }
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
        }
        url = f"{settings.EVOLUTION_API_SHARED_URL}/message/sendText/{instance_id}"

        logger.info(
            f"[evolution_sender] Sending messsa to : {url}\npayload: {payload}\nheaders: {headers}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        logger.info(
            f"[evolution_sender] Message sent successfully: {response.status_code} - {response.text}"
        )
        return response.json()
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
