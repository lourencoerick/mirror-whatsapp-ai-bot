from typing import List, Dict
from loguru import logger


def parse_whatsapp_message(payload: dict) -> List[Dict]:
    """
    Parses the WhatsApp Cloud API payload into internal message format(s).
    """

    messages = payload.get("messages", [])
    parsed = []

    for msg in messages:
        try:
            message_obj = {
                "content": msg["text"]["body"],
                "direction": "in",
                "account_id": 1,  # TODO: replace with real logic
                "inbox_id": 1,
                "conversation_id": 1,
                "contact_id": 1,
                "source_id": msg["id"],
                "status": 1,
                "content_attributes": {"source": "whatsapp"},
                "content_type": 1,
                "private": False,
            }
            parsed.append(message_obj)
        except Exception as e:
            logger.warning(f"[parser] Skipping invalid message: {msg} - {e}")
            continue

    return parsed
