# backend/app/api/routes/stripe/webhook.py

from fastapi import APIRouter, Request, Header, HTTPException, status, Response, Depends
from loguru import logger
import stripe  # Para stripe.error e stripe.Webhook
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .event_handler import (
    process_checkout_session_completed,
    process_invoice_payment_succeeded,
    process_customer_subscription_updated,
    process_customer_subscription_deleted,
    process_invoice_payment_failed,
)
from app.database import get_db
from app.config import get_settings

# Importaremos os serviços de processamento de webhook depois
# from app.services.stripe_webhook_service import handle_stripe_event

settings = get_settings()

router = APIRouter(
    prefix="/webhooks",  # Será /api/v1/webhooks se incluído no api_v1_router
    tags=["Webhooks"],
    # Este router NÃO deve ter dependências de autenticação globais da nossa API
)


@router.post(
    "/stripe", include_in_schema=False
)  # include_in_schema=False para não expor na doc OpenAPI pública
async def stripe_webhook_endpoint(
    request: Request,  # Usamos Request para obter o corpo bruto (raw body)
    stripe_signature: Optional[str] = Header(
        None, alias="Stripe-Signature"
    ),  # Header enviado pelo Stripe
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint to receive and process webhooks from Stripe.
    It verifies the signature of the incoming request to ensure it's from Stripe,
    then processes the event accordingly.
    """
    if not stripe_signature:
        logger.warning("Stripe webhook received without Stripe-Signature header.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    # Obter o corpo bruto da requisição
    payload = await request.body()

    # Segredo do endpoint de webhook (configurado no seu painel do Stripe e no .env)
    # Certifique-se de que STRIPE_WEBHOOK_SECRET está nas suas Settings
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    if not endpoint_secret:
        logger.error("STRIPE_WEBHOOK_SECRET is not configured in settings.")
        # Não retorne este erro para o Stripe, pois é um problema de configuração nosso.
        # Mas logue e talvez retorne um 500 genérico para o Stripe para que ele tente reenviar.
        # Para segurança, não revele a ausência do segredo.
        # No entanto, para desenvolvimento, um erro claro é útil.
        # Em produção, você pode querer apenas logar e retornar 200 para evitar que o Stripe desabilite o webhook.
        # Mas se não podemos verificar, não podemos processar.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured.",
        )

    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, endpoint_secret
        )
        logger.info(f"Stripe webhook event received: ID={event.id}, Type={event.type}")
    except ValueError as e:
        # Payload inválido
        logger.error(f"Stripe webhook error: Invalid payload. {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload"
        ) from e
    except stripe.error.SignatureVerificationError as e:  # type: ignore
        # Assinatura inválida
        logger.error(f"Stripe webhook error: Invalid signature. {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature"
        ) from e
    except Exception as e:
        logger.error(f"Stripe webhook error: Could not construct event. {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not construct event"
        ) from e

    # Log do evento completo para depuração inicial (pode ser muito verboso para produção constante)
    logger.debug(f"Stripe Event Full Payload: {event}")

    # TODO: Chamar um serviço para processar o 'event' com base no 'event.type'
    # Exemplo: await handle_stripe_event(event=event, db=db) # db precisaria ser injetado se o handler precisar
    # Por agora, apenas logamos e retornamos sucesso.

    try:
        if event.type == "checkout.session.completed":
            await process_checkout_session_completed(db=db, event=event)
        elif event.type == "invoice.payment_succeeded":
            await process_invoice_payment_succeeded(db=db, event=event)
        elif event.type == "customer.subscription.updated":
            await process_customer_subscription_updated(db=db, event=event)
        elif event.type == "customer.subscription.deleted":
            await process_customer_subscription_deleted(db=db, event=event)
        elif event.type == "invoice.payment_failed":
            await process_invoice_payment_failed(db=db, event=event)
        # Adicione outros tipos de evento que você quer tratar
        # elif event.type == "customer.subscription.trial_will_end":
        #     await process_trial_will_end(db=db, event=event)
        else:
            logger.info(f"Received unhandled Stripe event type: {event.type}")

        # Se chegou aqui sem exceções dos handlers, o processamento principal foi ok
        # O commit do DB é feito dentro de cada função de processamento se necessário
        # ou pode ser feito aqui uma vez se todas as operações forem bem-sucedidas.
        # Por segurança, cada handler pode fazer seu próprio commit/rollback.
        # Se um handler levanta exceção, o try/except abaixo pegará.

    except HTTPException:  # Re-lançar HTTPExceptions dos handlers
        raise
    except Exception as e:
        # Se qualquer handler de evento específico falhar com uma exceção não HTTP
        logger.exception(
            f"Error processing Stripe event {event.type} ({event.id}): {e}"
        )
        # Retornar 500 para o Stripe para que ele tente reenviar o evento.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook event processing failed internally.",
        ) from e

    return Response(
        status_code=status.HTTP_200_OK, content="Webhook received and acknowledged"
    )
