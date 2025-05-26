# backend/app/services/stripe_meter_service.py
import stripe  # type: ignore
from loguru import logger
from typing import Dict, Any  # Removido List pois não é usado aqui
from datetime import datetime, timezone  # Adicionado timezone

from app.config import get_settings

settings = get_settings()
# A chave API do Stripe deve ser configurada globalmente ou antes de cada chamada.
# Se você já configurou stripe.api_key em main.py ou similar, pode não ser necessário aqui.
# No entanto, para um serviço autocontido, é bom garantir que está definida.
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY
else:
    logger.warning(
        "Stripe secret key not configured. StripeMeterService may not function."
    )

# Não precisamos de uma classe StripeMeterEventPayload aqui, pois os argumentos são diretos.


async def report_usage_to_stripe_meter(
    event_name: str,
    stripe_customer_id: str,
    value: int,
    timestamp: datetime,  # Python datetime object (UTC é o ideal)
) -> bool:
    """
    Reports a single aggregated usage event to a Stripe Meter.

    Args:
        event_name: The `event_name` of the meter as configured in Stripe.
        stripe_customer_id: The Stripe Customer ID to bill for this usage.
        value: The integer amount of usage to report (e.g., total messages).
        timestamp: The Python datetime object representing the time of the usage
                   (or the end of an aggregation period). Stripe uses this for
                   allocating usage to the correct billing cycle.
                   It will be converted to a Unix timestamp.

    Returns:
        True if the event was successfully reported to Stripe, False otherwise.
        Stripe API errors are logged but not re-raised by default to allow
        the calling task to decide on retry logic for other items in a batch.
        Consider re-raising if a single failure should halt a batch.
    """
    if not settings.STRIPE_SECRET_KEY:  # Dupla verificação
        logger.error("Stripe secret key not configured. Cannot report meter events.")
        return False

    if not all(
        [
            event_name,
            stripe_customer_id,
            isinstance(value, int),
            isinstance(timestamp, datetime),
        ]
    ):
        logger.error(
            f"Invalid arguments for report_usage_to_stripe_meter: "
            f"event_name='{event_name}', customer='{stripe_customer_id}', value='{value}', ts_type='{type(timestamp)}'"
        )
        return False

    # Stripe espera um Unix timestamp (inteiro de segundos desde a época)
    # Certifique-se de que o timestamp está em UTC antes de converter, se possível,
    # ou que a conversão para timestamp() lide corretamente com o fuso horário.
    # Se o timestamp já for timezone-aware (como deveria ser), .timestamp() o converte para UTC.
    unix_timestamp = int(timestamp.timestamp())

    # O payload para a API de Meter Events é um pouco diferente do seu exemplo cURL.
    # O `event_name` e `timestamp` são parâmetros de nível superior.
    # O `payload` contém `stripe_customer_id` e `value`.
    # Referência: https://stripe.com/docs/api/metering/meter_events/create

    payload_for_stripe_api = {
        "stripe_customer_id": stripe_customer_id,
        "value": value,
        # Você pode adicionar mais metadados aqui se o seu medidor no Stripe os utilizar
        # "metadata": {"internal_batch_id": "some_id"}
    }

    logger.info(
        f"Reporting to Stripe Meter: event_name='{event_name}', "
        f"payload={payload_for_stripe_api}, timestamp_unix={unix_timestamp} ({timestamp.isoformat()})"
    )
    try:
        # A API correta é stripe.billing.MeterEvent.create
        meter_event_response = stripe.billing.MeterEvent.create(  # type: ignore
            event_name=event_name,
            payload=payload_for_stripe_api,
            timestamp=unix_timestamp,
        )
        # O objeto retornado não é o MeterEvent em si, mas um objeto de status/confirmação.
        # A documentação do Stripe para esta API específica não detalha muito a resposta de sucesso,
        # mas geralmente uma não-exceção indica sucesso.
        # Se houver um ID no objeto de resposta, pode ser útil logá-lo.
        response_id = getattr(
            meter_event_response, "id", "N/A"
        )  # Exemplo de como pegar um ID se existir
        logger.success(
            f"Successfully reported usage to Stripe Meter for customer {stripe_customer_id}. "
            f"Stripe Response ID (if any): {response_id}"
        )
        return True
    except stripe.error.StripeError as e:
        # Erros comuns: InvalidRequestError (ex: customer não existe, evento já reportado com mesmo timestamp e payload se não for permitido)
        # APIError, AuthenticationError, etc.
        logger.error(
            f"Stripe API error reporting meter event for customer {stripe_customer_id}, event '{event_name}': {e}. "
            f"HTTP Status: {e.http_status if hasattr(e, 'http_status') else 'N/A'}. "
            f"Stripe Code: {e.code if hasattr(e, 'code') else 'N/A'}."
        )
        # Para a tarefa ARQ, você pode querer que ela tente novamente se for um erro de rede.
        # Se for um erro 4xx (ex: dados inválidos), um retry não ajudará.
        # Por enquanto, retornamos False e a task decide.
        # raise e # Descomente se quiser que a tarefa ARQ falhe e tente novamente com base na sua política de retry.
        return False
    except Exception as e:
        logger.exception(
            f"Unexpected error reporting meter event for customer {stripe_customer_id}, event '{event_name}': {e}"
        )
        # raise e # Descomente para retry
        return False
