from fastapi import APIRouter, Request, HTTPException, status
from app.services.queue.iqueue import IQueue
from app.services.queue.redis_queue import RedisQueue
from app.services.parser.whatsapp_parser import parse_whatsapp_message
from app.services.parser.evolution_parser import parse_evolution_message
from loguru import logger

router = APIRouter()
queue: IQueue = RedisQueue(queue_name="message_queue")


@router.post("/webhook/whatsapp", status_code=status.HTTP_202_ACCEPTED)
async def whatsapp_webhook(request: Request):
    """
    Webhook to handle messages from WhatsApp (official API).
    Parses and enqueues each message for asynchronous processing.
    """
    try:
        payload = await request.json()
        logger.debug(f"[webhook] Raw WhatsApp payload: {payload}")

        parsed_messages = parse_whatsapp_message(payload)

        if not parsed_messages:
            raise HTTPException(status_code=400, detail="No valid messages found")

        for message in parsed_messages:
            queue.enqueue(message)
            logger.info(
                f"[webhook] Enqueued WhatsApp message: {message.get('source_id')}"
            )

        return {"status": "messages enqueued", "count": len(parsed_messages)}

    except HTTPException:
        raise
    except Exception:
        logger.exception("[webhook] Error while handling WhatsApp payload")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/webhook/evolution_whatsapp", status_code=status.HTTP_202_ACCEPTED)
async def evolution_whatsapp_webhook(request: Request):
    """
    Webhook to handle messages from Evolution API (unofficial WhatsApp).
    Parses and enqueues a single message for processing.
    """
    try:
        payload = await request.json()
        logger.debug(f"[webhook] Raw Evolution payload: {payload}")

        message = parse_evolution_message(payload)

        if not message:
            raise HTTPException(status_code=400, detail="No valid message found")

        queue.enqueue(message)
        logger.info(f"[webhook] Enqueued Evolution message: {message.get('source_id')}")

        return {"status": "message enqueued", "source_id": message.get("source_id")}

    except HTTPException:
        raise
    except Exception:
        logger.exception("[webhook] Error while handling Evolution payload")
        raise HTTPException(status_code=500, detail="Internal Server Error")
