# Em um novo arquivo de rotas para webhooks ou no seu arquivo de webhooks existente
from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    BackgroundTasks,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.services.repository import (
    whatsapp_cloud_config as whatsapp_cloud_config_repo,
)
from app.database import get_db


router = APIRouter(prefix="/webhooks/whatsapp", tags=["Webhooks - WhatsApp Cloud"])


@router.post(
    "/cloud/{phone_number_id_str}"
)  # Usando phone_number_id como string no path
async def handle_whatsapp_cloud_webhook(
    phone_number_id_str: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        f"Received WhatsApp Cloud webhook for Phone Number ID: {phone_number_id_str}"
    )
    raw_body = await request.body()

    # 1. TODO: Verificar a assinatura do Webhook (X-Hub-Signature-256) - MUITO IMPORTANTE PARA SEGURANÇA
    #    - Você precisará do seu App Secret da Meta.
    #    - Compare o hash HMAC-SHA256 do raw_body com o valor do header.

    try:
        payload = (
            await request.json()
        )  # Tenta parsear o JSON após verificar a assinatura
        logger.debug(f"Webhook payload: {payload}")
    except Exception as e:
        logger.error(f"Error parsing webhook JSON body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # 2. TODO: Encontrar a WhatsAppCloudConfig e a Account associada usando phone_number_id_str
    #    Ex: config = await whatsapp_cloud_config_repo.get_by_phone_number_id(db, phone_number_id_str)
    #    if not config:
    #        logger.warning(f"No WhatsAppCloudConfig found for phone_number_id: {phone_number_id_str}")
    #        raise HTTPException(status_code=404, detail="Configuration not found for this phone number ID")
    #    account_id = config.account_id
    #    inbox = await inbox_repo.find_by_whatsapp_cloud_config_id(db, config.id) (precisaria criar esta função)
    #    if not inbox:
    #        logger.error(f"No inbox found for WhatsAppCloudConfig ID: {config.id}")
    #        raise HTTPException(status_code=404, detail="Inbox not found for this configuration")

    # 3. TODO: Processar o payload do webhook (mensagens, status, etc.)
    #    - O payload da Meta tem uma estrutura específica com 'object', 'entry', 'changes', 'value', 'messages', etc.
    #    - Você precisará de schemas Pydantic para validar esse payload.
    #    - Disparar tarefas em background para processar mensagens e evitar bloquear a resposta do webhook.
    #    Ex: background_tasks.add_task(process_whatsapp_message, db, account_id, inbox.id, message_data_from_payload)

    # A Meta espera uma resposta 200 OK rapidamente.
    return Response(status_code=200)


@router.get("/cloud/{phone_number_id_str}")
async def verify_whatsapp_cloud_webhook(
    phone_number_id_str: str, request: Request, db: AsyncSession = Depends(get_db)
):
    mode = request.query_params.get("hub.mode")
    challenge = request.query_params.get("hub.challenge")
    token_from_meta = request.query_params.get("hub.verify_token")

    logger.info(
        f"Received webhook verification request for Phone Number ID: {phone_number_id_str}"
    )
    logger.info(
        f"Mode: {mode}, Challenge: {challenge}, Token from Meta: {token_from_meta}"
    )

    if not all([mode, challenge, token_from_meta]):
        logger.warning(
            "Missing hub.mode, hub.challenge, or hub.verify_token in query params."
        )
        raise HTTPException(
            status_code=400, detail="Missing required query parameters."
        )

    # Buscar a configuração do WhatsApp Cloud pelo phone_number_id
    config = await whatsapp_cloud_config_repo.get_config_by_phone_number_id(
        db, phone_number_id=phone_number_id_str
    )

    if not config:
        logger.warning(
            f"No WhatsAppCloudConfig found for phone_number_id: {phone_number_id_str} during verification."
        )
        # A Meta pode tentar verificar antes de você ter uma config, ou se o ID estiver errado.
        # Retornar 404 ou 403. 404 é mais informativo se a config não existe.
        raise HTTPException(
            status_code=404, detail="Configuration not found for this phone number ID."
        )

    stored_verify_token = config.webhook_verify_token
    logger.debug(
        f"Stored verify token for {phone_number_id_str}: {stored_verify_token}"
    )

    if mode == "subscribe" and token_from_meta == stored_verify_token:
        logger.info(f"Webhook verification successful for {phone_number_id_str}.")
        return Response(content=challenge, media_type="text/plain", status_code=200)
    else:
        logger.warning(
            f"Webhook verification failed for {phone_number_id_str}. "
            f"Mode: {mode} (expected 'subscribe'), "
            f"Token from Meta: '{token_from_meta}', Stored Token: '{stored_verify_token}'"
        )
        raise HTTPException(status_code=403, detail="Webhook verification failed.")
