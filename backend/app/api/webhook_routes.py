from fastapi import APIRouter, Request, HTTPException, status
from app.services.queue.iqueue import IQueue
from app.services.queue.redis_queue import RedisQueue
from app.services.parser.whatsapp_parser import parse_whatsapp_message
from app.services.parser.evolution_webhook import parse_evolution_webhook
from loguru import logger

router = APIRouter()
queue: IQueue = RedisQueue()


@router.post("/webhook/whatsapp", status_code=status.HTTP_202_ACCEPTED)
async def whatsapp_webhook(request: Request):
    """
    Receives incoming WhatsApp messages via webhook and enqueues them for async processing.
    """
    try:
        payload = await request.json()
        logger.debug(f"[webhook] Received raw payload: {payload}")

        parsed_messages = parse_whatsapp_message(payload)

        if not parsed_messages:
            raise HTTPException(status_code=400, detail="No valid messages found")

        for message in parsed_messages:
            queue.enqueue(message)
            logger.info(f"[webhook] Enqueued message: {message.get('source_id')}")

        return {"status": "messages enqueued", "count": len(parsed_messages)}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[webhook] Unexpected error during processing")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/webhook/evolution_whatsapp", status_code=status.HTTP_202_ACCEPTED)
async def evolution_whatsapp_webhook(request: Request):
    """
    Receives incoming WhatsApp messages via webhook and enqueues them for async processing.
    """
    try:
        payload = await request.json()
        logger.debug(f"[webhook] Received raw payload: {payload}")

        parsed_message = parse_evolution_webhook(payload)

        if not parsed_message:
            raise HTTPException(status_code=400, detail="No valid messages found")

        queue.enqueue(parsed_message)
        logger.info(f"[webhook] Enqueued message: {parsed_message.get('source_id')}")

        return {
            "status": "message enqueued",
            "source_id": parsed_message.get("source_id"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[webhook] Unexpected error during processing")
        raise HTTPException(status_code=500, detail="Internal Server Error")
