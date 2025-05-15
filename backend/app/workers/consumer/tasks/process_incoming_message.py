# app/workers/tasks/message_processing_tasks.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import AsyncSessionLocal  # Sua factory de sessão SQLAlchemy
from loguru import logger
from pydantic import ValidationError  # Para capturar erros de validação do Pydantic
from typing import Optional, List

# Schemas
from app.api.schemas.queue_payload import (
    IncomingMessagePayload,
)  # Payload da fila ARQ
from app.api.schemas.webhooks.whatsapp_cloud import (
    WhatsAppValue as WhatsAppCloudValueSchema,
)
from app.api.schemas.internal_messaging import (
    InternalIncomingMessageDTO,
)  # Nosso DTO padronizado

# Funções de Transformação
from app.services.parser.message_webhook_parser import (
    transform_whatsapp_cloud_to_internal_dto,
    transform_evolution_api_to_internal_dto,
)

# Lógica de Serviço Principal
from app.services.parser.message_processing import process_incoming_message_logic

from app.services.debounce.message_debounce import MessageDebounceService


async def process_incoming_message_task(ctx: dict, arq_payload_dict: dict):
    """
    ARQ task to process an incoming message enqueued by a webhook endpoint.

    This task:
    1. Validates the ArqIncomingMessagePayload received from the queue.
    2. Extracts the 'external_raw_message' (which is Meta's 'value' object for Cloud API).
    3. Validates this 'value' object.
    4. Iterates over individual messages within the 'value' object.
    5. For each message, calls the appropriate transformation function (passing the
       individual message and associated contact profiles from the 'value' object).
    6. If transformation is successful, calls the core message processing logic.
    7. Handles database session management and error logging.
    """
    task_id = ctx.get("job_id", "unknown_arq_job_id")
    log_prefix = f"ARQ Task (ID: {task_id}):"

    business_id_for_log = arq_payload_dict.get(
        "business_identifier", "unknown_business_id"
    )
    source_api_for_log = arq_payload_dict.get("source_api", "unknown_source")
    logger.info(
        f"{log_prefix} Starting processing for source_api='{source_api_for_log}', business_identifier='{business_id_for_log}'"
    )
    logger.debug(f"{log_prefix} Raw ARQ payload dict: {arq_payload_dict}")

    db_session_factory = ctx.get("db_session_factory")
    if not db_session_factory:
        logger.error(
            f"{log_prefix} db_session_factory not found in ARQ context. Cannot process message."
        )
        raise Exception(
            "ARQ Worker Misconfiguration: Database session factory not available."
        )

    debounce_service: Optional[MessageDebounceService] = ctx.get(
        "message_debounce_service_instance"
    )
    if not debounce_service:
        logger.warning(
            f"{log_prefix} MessageDebounceService instance not found in ARQ context. Debounce functionality will be skipped."
        )

    async with db_session_factory() as db:  # Nova sessão de DB para esta tarefa
        processed_dtos_count = 0
        try:
            # 1. Validar o payload da fila ARQ
            try:
                arq_payload = IncomingMessagePayload.model_validate(arq_payload_dict)
            except ValidationError as e_val_arq:
                logger.error(
                    f"{log_prefix} Invalid IncomingMessagePayload structure: {e_val_arq.errors()}. Payload: {arq_payload_dict}"
                )
                return  # Erro de payload, não retentar

            logger.debug(
                f"{log_prefix} Validated IncomingMessagePayload. Source: {arq_payload.source_api}"
            )

            # external_raw_message é o objeto 'value' da Meta (como um dict) ou o payload da Evolution
            external_value_or_message_dict = arq_payload.external_raw_message

            internal_dto_list: List[InternalIncomingMessageDTO] = []

            if arq_payload.source_api == "simulation":
                if arq_payload.internal_dto_partial_data:
                    try:
                        internal_dto = InternalIncomingMessageDTO.model_validate(
                            arq_payload.internal_dto_partial_data
                        )
                        logger.info(
                            f"{log_prefix} Successfully created InternalIncomingMessageDTO from simulation override data."
                        )
                        internal_dto_list.append(internal_dto)
                    except ValidationError as e_val_dto:
                        logger.error(
                            f"{log_prefix} Invalid internal_dto_partial_data for simulation: {e_val_dto.errors()}. Payload: {arq_payload.internal_dto_partial_data}"
                        )
                        return  # Erro de payload, não retentar
                else:
                    logger.error(
                        f"{log_prefix} 'internal_dto_partial_data' missing for source_api='simulation'."
                    )
                    return
            elif arq_payload.source_api == "whatsapp_cloud":
                try:
                    # Validar o external_value_or_message_dict para o schema WhatsAppValue
                    # Este 'value' object contém as listas 'messages' e 'contacts'
                    validated_value_object = WhatsAppCloudValueSchema.model_validate(
                        external_value_or_message_dict
                    )
                except ValidationError as e_val_value:
                    logger.error(
                        f"{log_prefix} Invalid WhatsApp Cloud 'value' object structure: {e_val_value.errors()}. Payload: {external_value_or_message_dict}"
                    )
                    return  # Erro de payload, não retentar

                messages_from_value = validated_value_object.messages or []
                # contacts_from_value pode ser None, a função de transformação deve lidar com isso
                contacts_from_value_dicts = (
                    [
                        c.model_dump(exclude_none=True)
                        for c in validated_value_object.contacts
                    ]
                    if validated_value_object.contacts
                    else None
                )

                logger.info(
                    f"{log_prefix} Found {len(messages_from_value)} message(s) in WhatsApp Cloud 'value' object to transform."
                )

                for (
                    single_meta_message_obj
                ) in (
                    messages_from_value
                ):  # single_meta_message_obj é WhatsAppMessageSchema
                    transformed_dto = await transform_whatsapp_cloud_to_internal_dto(
                        db=db,
                        business_phone_number_id=arq_payload.business_identifier,
                        single_meta_message_dict=single_meta_message_obj.model_dump(
                            by_alias=True, exclude_none=True
                        ),  # Passar como dict
                        meta_contacts_list_dicts=contacts_from_value_dicts,
                    )
                    if transformed_dto:
                        internal_dto_list.append(transformed_dto)
                    else:
                        logger.warning(
                            f"{log_prefix} Transformation returned None for a WhatsApp Cloud message. "
                            f"WAMID (if available): {single_meta_message_obj.id}. Skipping this specific message."
                        )

            elif arq_payload.source_api == "whatsapp_evolution":
                # Supondo que external_raw_message para Evolution seja o dict da mensagem individual
                # e que transform_evolution_api_to_internal_dto lide com isso.
                # Se Evolution também agrupar mensagens ou tiver informações de contato separadas, ajuste aqui.
                transformed_dto = await transform_evolution_api_to_internal_dto(
                    db=db,
                    internal_evolution_instance_uuid=arq_payload.business_identifier,
                    raw_evolution_webhook_payload_dict=external_value_or_message_dict,  # Assumindo que é a mensagem individual
                )
                if transformed_dto:
                    internal_dto_list.append(transformed_dto)
                else:
                    logger.warning(
                        f"{log_prefix} Transformation returned None for an Evolution API message. "
                        f"Raw payload: {external_value_or_message_dict}. Skipping this message."
                    )
            else:
                logger.error(
                    f"{log_prefix} Unknown source_api '{arq_payload.source_api}' in ArqIncomingMessagePayload."
                )
                return

            if not internal_dto_list:
                logger.warning(
                    f"{log_prefix} No messages were successfully transformed from ARQ payload. Business ID: {arq_payload.business_identifier}"
                )
                # Se a transformação falhou para todas as mensagens (ou não havia mensagens),
                # não há nada para commitar ou dar rollback especificamente desta fase.
                return

            # Processar cada DTO transformado. Cada chamada a process_incoming_message_logic
            # idealmente gerencia sua própria sub-transação ou contribui para a transação geral da tarefa.
            # Se process_incoming_message_logic faz commit/rollback, então cada DTO é processado atomicamente.
            for internal_dto_item in internal_dto_list:
                try:
                    logger.info(
                        f"{log_prefix} Processing transformed DTO for external_id: {internal_dto_item.external_message_id}"
                    )
                    await process_incoming_message_logic(
                        db=db,
                        internal_message=internal_dto_item,
                        debounce_service=debounce_service,
                    )
                    processed_dtos_count += 1
                except Exception as e_logic:
                    # Logar o erro específico do process_incoming_message_logic mas continuar com outros DTOs se houver
                    logger.error(
                        f"{log_prefix} Error processing DTO for external_id {internal_dto_item.external_message_id}: {e_logic}",
                        exc_info=True,
                    )
                    # Não fazer rollback aqui para não afetar DTOs já processados com sucesso na mesma tarefa ARQ,
                    # assumindo que process_incoming_message_logic faz seu próprio rollback em caso de falha.
                    # Se process_incoming_message_logic não faz rollback e levanta exceção,
                    # a exceção será capturada pelo try/except mais externo da tarefa.

            if processed_dtos_count > 0 and processed_dtos_count == len(
                internal_dto_list
            ):
                logger.info(
                    f"{log_prefix} All ({processed_dtos_count}) DTOs from ARQ payload processed successfully for business_id: {arq_payload.business_identifier}"
                )
            elif processed_dtos_count > 0:
                logger.warning(
                    f"{log_prefix} Partially processed DTOs ({processed_dtos_count}/{len(internal_dto_list)}) for business_id: {arq_payload.business_identifier}"
                )
            else:
                logger.error(
                    f"{log_prefix} No DTOs were successfully processed for business_id: {arq_payload.business_identifier}"
                )

        except Exception as e_task_main:
            logger.error(
                f"{log_prefix} Unhandled exception during ARQ task execution for "
                f"business_identifier='{arq_payload_dict.get('business_identifier')}'. Error: {e_task_main}",
                exc_info=True,
            )
            await db.rollback()
            raise
