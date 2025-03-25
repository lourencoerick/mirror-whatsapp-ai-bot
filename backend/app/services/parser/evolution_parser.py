from typing import Dict, Optional
from loguru import logger
from app.api.schemas.message import MessageCreate


def parse_evolution_message(payload: Dict) -> Optional[Dict]:
    """
    Parses the incoming Evolution webhook and extracts raw message info.

    Returns:
        Dict with message content and metadata, or None if invalid.
    """
    try:
        event = payload.get("event", "")
        if event != "messages.upsert":
            logger.warning(f"[evolution_parser] Unsupported event: {event}")
            return None

        data = payload.get("data", {})
        key = data.get("key", {})
        content = data.get("message", {}).get("conversation")
        source_id = key.get("id")
        remote_jid = key.get("remoteJid")
        timestamp = data.get("messageTimestamp")

        if not content or not source_id or not remote_jid or not timestamp:
            logger.warning("[evolution_parser] Missing required message fields")
            return None

        direction = "out" if key.get("fromMe") else "in"
        content_type = data.get("messageType", "text")

        parsed = {
            "content": content,
            "direction": direction,
            "source_id": source_id,
            "remote_jid": remote_jid,
            "message_timestamp": timestamp,
            "content_type": content_type,
            "content_attributes": {
                "provider": "evolution",
                "instance_id": data.get("instanceId"),
                "sender": payload.get("sender"),
                "raw_message_type": data.get("messageType"),
            },
        }

        return parsed

    except Exception:
        logger.exception("[evolution_parser] Failed to parse webhook")
        return None
