import requests
from loguru import logger


def send_message(message: dict) -> None:
    """
    Sends a text message using the WhatsApp official API (Graph API).

    Args:
        message (dict): A dictionary containing the message payload with the following fields:
            - number (str): Recipient phone number including country code.
            - text (str): Text content of the message.
            - token (str): Authorization token for WhatsApp API.
    """
    try:
        payload = {
            "messaging_product": "whatsapp",
            "to": message["number"],
            "type": "text",
            "text": {"body": message["text"]},
        }
        headers = {
            "Authorization": f"Bearer {message['token']}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            "https://graph.facebook.com/v19.0/YOUR_PHONE_NUMBER_ID/messages",
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        logger.info(
            f"[whatsapp_sender] Message sent successfully: {response.status_code} - {response.text}"
        )
    except Exception as e:
        logger.error(f"[whatsapp_sender] Failed to send message: {e}")
