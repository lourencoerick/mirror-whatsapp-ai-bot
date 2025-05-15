# Em um novo arquivo de rotas para webhooks ou no seu arquivo de webhooks existente
from fastapi import (
    APIRouter,
    Request,
    Depends,
    HTTPException,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from typing import Optional
from pydantic import ValidationError
from arq.connections import ArqRedis
import hashlib
import hmac
import json

from app.api.schemas.webhooks.whatsapp_cloud import (
    WhatsAppCloudWebhookPayload,
)
from app.api.schemas.queue_payload import IncomingMessagePayload

from app.services.repository import (
    whatsapp_cloud_config as whatsapp_cloud_config_repo,
)
from app.core.arq_manager import get_arq_pool
from app.database import get_db
from app.config import get_settings, Settings

from app.core.wake_workers import wake_worker

settings: Settings = get_settings()


router = APIRouter(prefix="/webhooks/whatsapp", tags=["Webhooks - WhatsApp Cloud"])


@router.post("/cloud/{phone_number_id_str}")
async def handle_whatsapp_cloud_webhook(
    phone_number_id_str: str,
    request: Request,
):
    """
    Handles incoming POST requests from WhatsApp Cloud API webhooks.
    Verifies the signature, validates the payload, and enqueues messages/events
    for asynchronous processing via ARQ.
    """
    logger.info(
        f"Received WhatsApp Cloud webhook POST for Phone Number ID: {phone_number_id_str}"
    )

    raw_body = await request.body()

    # --- 1. Verify Webhook Signature (Essential for Security) ---
    signature_header = request.headers.get("X-Hub-Signature-256")

    if not settings.META_APP_SECRET:
        logger.error(
            "CRITICAL: META_APP_SECRET is not configured. Webhook signature cannot be verified."
        )
        if settings.ENVIRONMENT not in [
            "development",
            "test",
        ]:
            logger.critical(
                "Signature verification skipped due to missing META_APP_SECRET in non-dev environment. THIS IS A SECURITY RISK."
            )
            # Retornar 200 para a Meta para não desabilitar o webhook, mas internamente é uma falha.
            return Response(
                status_code=200,
                content="Webhook accepted but server configuration error (secret missing).",
            )
        logger.warning(
            "META_APP_SECRET not set. Skipping signature verification (DEVELOPMENT/TEST ONLY)."
        )
    elif not signature_header:
        logger.warning("Missing X-Hub-Signature-256 header. Denying request.")
        raise HTTPException(status_code=403, detail="Missing signature header.")
    else:
        try:
            hash_method, received_hash = signature_header.split("=", 1)
            if hash_method.lower() != "sha256":
                logger.warning(f"Unsupported hash method in signature: {hash_method}")
                raise HTTPException(
                    status_code=400, detail="Unsupported signature hash method."
                )

            expected_hash = hmac.new(
                settings.META_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(expected_hash, received_hash):
                logger.warning("Webhook signature mismatch. Denying request.")
                raise HTTPException(
                    status_code=403, detail="Invalid webhook signature."
                )
            logger.info("Webhook signature verified successfully.")
        except ValueError:  # Erro no split("=", 1)
            logger.warning("Malformed X-Hub-Signature-256 header.")
            raise HTTPException(status_code=400, detail="Malformed signature header.")
        except Exception as sig_exc:  # Outras exceções
            logger.error(
                f"Unexpected error during signature verification: {sig_exc}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="Error verifying signature."
            ) from sig_exc

    # --- 2. Parse and Validate JSON Payload ---
    try:
        payload_dict = json.loads(raw_body.decode("utf-8"))
        logger.debug(f"Webhook raw payload dict: {payload_dict}")
        webhook_data = WhatsAppCloudWebhookPayload.model_validate(payload_dict)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing webhook JSON body: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from e
    except ValidationError as e:
        logger.error(f"Webhook payload Pydantic validation error: {e.errors()}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid webhook payload structure: {json.loads(e.json())}",
        ) from e

    # --- 3. Get ARQ Client ---
    arq_client: Optional[ArqRedis] = await get_arq_pool()
    if not arq_client:
        logger.critical(
            "ARQ client (pool) is not available. Cannot enqueue webhook events for processing."
        )
        # É importante retornar 200 para a Meta para evitar que eles desabilitem seu webhook.
        # A mensagem será perdida se não houver um mecanismo de fallback ou dead-letter queue.
        return Response(
            status_code=200,
            content="Webhook accepted, but internal processing queue is currently unavailable.",
        )

    # --- 4. Process Entries and Changes, then Enqueue Tasks ---
    business_identifier_from_path = phone_number_id_str
    phone_number_id_from_payload = webhook_data.get_phone_number_id()

    if (
        phone_number_id_from_payload
        and phone_number_id_from_payload != business_identifier_from_path
    ):
        logger.warning(
            f"Path phone_number_id '{business_identifier_from_path}' does not match "
            f"payload metadata phone_number_id '{phone_number_id_from_payload}'. "
            f"Using path parameter as business_identifier."
        )

    if webhook_data.entry:
        for entry in webhook_data.entry:
            if entry.changes:
                for change in entry.changes:
                    if change.field == "messages":
                        value_object = change.value
                        if value_object.messages:
                            logger.info(
                                f"Found {len(value_object.messages)} message(s) in change.value. "
                                f"Enqueuing the 'value' object for processing. Business ID: {business_identifier_from_path}"
                            )
                            try:

                                arq_task_payload = IncomingMessagePayload(
                                    source_api="whatsapp_cloud",
                                    business_identifier=business_identifier_from_path,
                                    external_raw_message=value_object.model_dump(
                                        by_alias=True, exclude_none=True
                                    ),
                                )

                                await arq_client.enqueue_job(
                                    "process_incoming_message_task",
                                    arq_payload_dict=arq_task_payload.model_dump(),
                                    _queue_name=settings.MESSAGE_QUEUE_NAME,
                                )
                                logger.info(
                                    f"Enqueued 'value' object (containing messages) for processing. Business ID: {business_identifier_from_path}"
                                )
                                await wake_worker(
                                    settings.MESSAGE_CONSUMER_WORKER_INTERNAL_URL
                                )
                                await wake_worker(settings.AI_REPLIER_INTERNAL_URL)
                                await wake_worker(
                                    settings.RESPONSE_SENDER_WORKER_INTERNAL_URL
                                )
                            except Exception as e_enqueue:
                                logger.error(
                                    f"Failed to create ArqIncomingMessagePayload or enqueue 'value' object for messages: {e_enqueue}",
                                    exc_info=True,
                                )
                                # Considerar estratégia de fallback se o enfileiramento falhar

                        # Processar atualizações de status de mensagens enviadas (se houver)
                        if value_object.statuses:
                            for (
                                status_payload_obj
                            ) in (
                                value_object.statuses
                            ):  # status_payload_obj é WhatsAppMessageStatus
                                logger.info(
                                    f"Received message status update: WAMID {status_payload_obj.id} to Status {status_payload_obj.status}"
                                )
                                # TODO: Implementar enfileiramento para uma tarefa de processamento de status.
                                # O payload para esta tarefa ARQ de status precisaria do business_identifier
                                # e do status_payload_obj.model_dump().
                                # Ex:
                                # status_arq_payload = ArqStatusUpdatePayload( # Definir este schema
                                #     source_api="whatsapp_cloud",
                                #     business_identifier=business_identifier_from_path,
                                #     status_details=status_payload_obj.model_dump(exclude_none=True)
                                # )
                                # await arq_client.enqueue_job(
                                #     "process_whatsapp_status_update_task", # Nova tarefa ARQ
                                #     status_update_dict=status_arq_payload.model_dump(),
                                #     _queue_name=settings.STATUS_PROCESSING_ARQ_QUEUE_NAME # Nova fila?
                                # )
                                pass  # Por agora, apenas logamos.

                        # Processar erros reportados pela Meta (se houver)
                        if value_object.errors:
                            for (
                                error_payload_obj
                            ) in (
                                value_object.errors
                            ):  # error_payload_obj é um dict ou um schema Pydantic
                                logger.error(
                                    f"Received error object from Meta webhook's 'value': {error_payload_obj}"
                                )
                                # TODO: Lógica para lidar com esses erros (ex: notificar admin, logar detalhadamente)
                                # Pode ser útil enfileirar para uma tarefa de tratamento de erros também.
                                pass
                    else:
                        logger.debug(
                            f"Change field is not 'messages' (actual: '{change.field}'). Skipping this change."
                        )
            else:
                logger.debug(
                    f"No changes array in entry ID {entry.id}. Skipping this entry."
                )
    else:
        logger.debug("No entries in webhook data. Nothing to process.")

    # --- 5. Return 200 OK to Meta ---
    # É crucial retornar 200 OK rapidamente, mesmo que haja falhas internas no enfileiramento,
    # para evitar que a Meta desabilite seu webhook. Erros internos devem ser logados e monitorados.
    return Response(status_code=200)


@router.get("/cloud/{phone_number_id_str}")
async def verify_whatsapp_cloud_webhook(
    phone_number_id_str: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handles GET requests from Meta to verify the webhook endpoint.
    Compares the 'hub.verify_token' from the query parameters with the
    one stored in the database for the given phone_number_id.
    """
    mode = request.query_params.get("hub.mode")
    challenge = request.query_params.get("hub.challenge")
    token_from_meta = request.query_params.get("hub.verify_token")

    logger.info(
        f"Received webhook GET verification request for Phone Number ID: {phone_number_id_str}"
    )
    logger.info(
        f"Query Params - hub.mode: {mode}, hub.challenge: {challenge}, hub.verify_token: {token_from_meta}"
    )

    if not all([mode, challenge, token_from_meta]):
        logger.warning(
            "Missing hub.mode, hub.challenge, or hub.verify_token in GET request query params."
        )
        # Meta espera um erro se os parâmetros estiverem faltando, 400 é apropriado.
        raise HTTPException(
            status_code=400,
            detail="Missing required query parameters for webhook verification.",
        )

    config = await whatsapp_cloud_config_repo.get_config_by_phone_number_id(
        db, phone_number_id=phone_number_id_str
    )

    if not config:
        logger.warning(
            f"No WhatsAppCloudConfig found for phone_number_id: {phone_number_id_str} during GET verification."
        )
        # Se a configuração não existe, a Meta não pode verificar. 404 é apropriado.
        raise HTTPException(
            status_code=404, detail="Configuration not found for this phone number ID."
        )

    stored_verify_token = config.webhook_verify_token
    logger.debug(
        f"Stored webhook_verify_token for {phone_number_id_str} from DB: '{stored_verify_token}'"
    )

    if mode == "subscribe" and token_from_meta == stored_verify_token:
        logger.info(
            f"Webhook GET verification successful for {phone_number_id_str}. Responding with challenge."
        )
        return Response(content=challenge, media_type="text/plain", status_code=200)
    else:
        logger.warning(
            f"Webhook GET verification failed for {phone_number_id_str}. "
            f"Mode: '{mode}' (expected 'subscribe'), "
            f"Token from Meta: '{token_from_meta}', Stored DB Token: '{stored_verify_token}'"
        )
        # Se a verificação falhar, a Meta espera um erro 403.
        raise HTTPException(
            status_code=403,
            detail="Webhook verification failed due to token mismatch or invalid mode.",
        )
