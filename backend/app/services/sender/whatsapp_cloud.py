# app/services/sender/whatsapp_cloud.py

import httpx
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.models.channels.whatsapp_cloud_config import (
    WhatsAppCloudConfig,
)  # Modelo da config
from app.core.security import decrypt_logical_token

# Importar os schemas Pydantic para o payload da Meta, se definidos
from app.api.schemas.external.whatsapp_cloud import (
    MetaSendTextMessagePayload,
    MetaTextObject,
)
from app.config import get_settings, Settings

settings: Settings = get_settings()
WHATSAPP_GRAPH_API_VERSION = "v22.0"
WHATSAPP_GRAPH_API_BASE_URL = "https://graph.facebook.com"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def send_text_message(
    message_content: str,
    recipient_phone_number: str,
    config: WhatsAppCloudConfig,
) -> dict:
    """
    Sends a text message using the WhatsApp Cloud API.

    Args:
        message_content: The text content of the message.
        recipient_phone_number: The recipient's phone number in E.164 format.
        config: The WhatsAppCloudConfig object containing API credentials.

    Returns:
        A dictionary representing the JSON response from Meta's API.

    Raises:
        httpx.HTTPStatusError: If Meta's API returns an error status code.
        httpx.RequestError: If a network or connection error occurs.
        Exception: For other unexpected errors.
    """
    if not WHATSAPP_GRAPH_API_VERSION:
        logger.error("WHATSAPP_GRAPH_API_VERSION is not configured in settings.")
        raise ValueError("WhatsApp API version is not configured.")
    if not config.phone_number_id:  # O ID do número da SUA empresa
        logger.error(
            f"WhatsAppCloudConfig (ID: {config.id}) is missing phone_number_id."
        )
        raise ValueError("Business phone_number_id is missing in WhatsAppCloudConfig.")

    try:
        access_token = decrypt_logical_token(config.encrypted_access_token)
    except Exception as e_decrypt:
        logger.error(
            f"Failed to decrypt access token for WhatsAppCloudConfig ID {config.id}: {e_decrypt}"
        )
        raise ValueError("Could not decrypt access token.") from e_decrypt

    api_url = f"{WHATSAPP_GRAPH_API_BASE_URL}/{WHATSAPP_GRAPH_API_VERSION}/{config.phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    text_object = MetaTextObject(body=message_content)
    payload = MetaSendTextMessagePayload(to=recipient_phone_number, text=text_object)
    payload_dict = payload.model_dump(
        by_alias=True
    )  # by_alias para garantir nomes corretos dos campos JSON

    logger.info(
        f"[whatsapp_cloud_sender] Sending text message to: {recipient_phone_number} "
        f"via Business Phone ID: {config.phone_number_id}"
    )
    logger.debug(f"[whatsapp_cloud_sender] URL: {api_url}")
    logger.trace(f"[whatsapp_cloud_sender] Payload: {payload_dict}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                api_url,
                json=payload_dict,
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            response_data = response.json()
            logger.info(
                f"[whatsapp_cloud_sender] Text message sent successfully to {recipient_phone_number}. "
                f"Response Status: {response.status_code}. Meta Message ID(s): "
                f"{[msg.get('id') for msg in response_data.get('messages', [])]}"
            )
            return response_data
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[whatsapp_cloud_sender] HTTP error sending message to {recipient_phone_number}: "
                f"{e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            logger.warning(
                f"[whatsapp_cloud_sender] Retriable request failure sending to {recipient_phone_number}: {type(e).__name__} - {e}. "
                f"Attempt {e.request.extensions.get('retry_context', {}).get('attempt_number', '?')}."
            )
            raise
        except Exception as e:
            logger.exception(
                f"[whatsapp_cloud_sender] Unexpected error sending message to {recipient_phone_number}: {e}"
            )
            raise
