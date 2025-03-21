from fastapi import APIRouter

router = APIRouter()


@router.post("/webhook/whatsapp")
async def receive_whatsapp_webhook():
    # lógica de recebimento e parsing da mensagem
    pass
