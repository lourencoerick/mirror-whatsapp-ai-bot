from typing import Dict, Optional
from loguru import logger


def parse_evolution_message(payload: Dict) -> Optional[Dict]:
    """
    Parses incoming webhook payload from Evolution API into internal message format.

    Args:
        payload (Dict): Raw webhook from Evolution.

    Returns:
        Optional[Dict]: Parsed message ready for enqueueing, or None if invalid.
    """
    try:
        event = payload.get("event", "")
        if event not in ["messages.upsert"]:
            logger.warning(f"[parse] Invalid event type: {event}")
            return None
        data = payload.get("data", {})
        key = data.get("key", {})
        message_content = data.get("message", {}).get("conversation")

        if not message_content or not key.get("id") or not key.get("remoteJid"):
            logger.warning("[parse] Missing required fields in payload")
            return None

        # Extract direction: true = fromMe (outgoing), false = incoming
        direction = "out" if key.get("fromMe", False) else "in"

        # Remove domain from contact JID (e.g., "5511941986775@s.whatsapp.net")
        raw_contact = key.get("remoteJid", "")
        contact_number = (
            raw_contact.split("@")[0] if "@" in raw_contact else raw_contact
        )

        parsed = {
            "content": message_content,
            "direction": direction,
            "source_id": key.get("id"),
            "contact_id": 2,  # Placeholder for now
            "account_id": 1,  # Placeholder for now
            "inbox_id": 1,  # Placeholder for now
            "conversation_id": 1,  # Placeholder for now
            "status": 1,
            "content_type": 1,  # Assuming 1 = text
            "private": 0,
            "content_attributes": {
                "provider": "evolution",
                "sender": payload.get("sender"),
                "instance_id": data.get("instanceId"),
                "message_type": data.get("messageType"),
                "timestamp": data.get("messageTimestamp"),
            },
        }

        logger.debug(f"[parse] Parsed message: {parsed}")
        return parsed

    except Exception:
        logger.exception("[parse] Failed to parse Evolution webhook")
        return None
