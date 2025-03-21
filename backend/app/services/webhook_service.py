def parse_whatsapp_payload(payload: dict) -> dict:
    """Extracts relevant information from the WhatsApp API payload."""
    try:
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    return {
                        "phone_number": message["from"],
                        "message_id": message["id"],
                        "text": message.get("text", {}).get("body", ""),
                        "timestamp": message["timestamp"],
                    }

    except Exception as e:
        print(f"Error parsing WhatsApp payload: {e}")

    return None  # Return None if parsing fails
