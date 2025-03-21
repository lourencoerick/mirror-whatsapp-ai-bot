from fastapi import APIRouter, HTTPException, Request, Depends
import json
from loguru import logger
from app.services.queue.iqueue import IQueue
from app.services.queue.redis_queue import RedisQueue
from app.services.webhook_service import parse_whatsapp_payload

router = APIRouter()

# Inject queue dependency (can be replaced in the future)
queue: IQueue = RedisQueue()


@router.post("/webhook/whatsapp")
async def receive_whatsapp_webhook(request: Request):
    """Webhook endpoint to receive WhatsApp messages."""
    try:
        payload = await request.json()
        logger.debug(f"[webhook] Payload received: {payload}")

        # Parse the incoming WhatsApp payload
        parsed_message = parse_whatsapp_payload(payload)
        if not parsed_message:
            logger.warning("[webhook] Invalid payload structure")
            raise HTTPException(status_code=400, detail="Invalid payload")

        # Enqueue the parsed message for processing
        queue.enqueue(parsed_message)
        logger.info(f"[webhook] Message enqueued: {parsed_message}")

        return {"status": "success", "message": "Message enqueued for processing"}

    except Exception as e:
        logger.exception("[webhook] Unexpected error")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
