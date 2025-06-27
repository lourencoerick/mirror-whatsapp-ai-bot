# app/services/helper/circuit_breaker.py

from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta
from loguru import logger

from app.models.conversation import Conversation, ConversationStatusEnum

# Definir as constantes aqui para que sejam fáceis de ajustar
PING_PONG_LIMIT = 4
PING_PONG_WINDOW_SECONDS = 25


class PingPongLimitExceeded(Exception):
    """Custom exception to signal that the circuit breaker has tripped."""

    pass


async def check_and_update_ping_pong_circuit_breaker(
    db: AsyncSession, conversation: Conversation, log_prefix: str = ""
) -> None:
    """
    Checks and updates the ping-pong circuit breaker for a conversation.

    This function updates the conversation's ping-pong counter and timestamp.
    If the limit is exceeded, it changes the conversation status and raises
    a specific exception to halt further processing.

    Args:
        db: The active SQLAlchemy async session.
        conversation: The conversation object to check.
        log_prefix: A prefix for log messages for better context.

    Raises:
        PingPongLimitExceeded: If the consecutive message limit is reached.
    """
    now = datetime.now(timezone.utc)

    # Se já houve uma mensagem do agente e foi recentemente...
    if conversation.last_agent_message_timestamp:
        time_since_last = now - conversation.last_agent_message_timestamp
        if time_since_last < timedelta(seconds=PING_PONG_WINDOW_SECONDS):
            # Dentro da janela, incrementa o contador
            conversation.ping_pong_count += 1
        else:
            # Fora da janela, reseta o contador
            conversation.ping_pong_count = 1
    else:
        # Primeira mensagem do agente nesta "sequência"
        conversation.ping_pong_count = 1

    # Atualiza o timestamp da última mensagem do agente para AGORA
    conversation.last_agent_message_timestamp = now
    db.add(conversation)
    await db.flush()  # Salva as mudanças no contador e timestamp na sessão

    logger.info(
        f"{log_prefix} Ping-pong count for ConvID {conversation.id} is now: {conversation.ping_pong_count}"
    )

    # Verificar se o limite foi excedido
    if conversation.ping_pong_count > PING_PONG_LIMIT:
        logger.warning(
            f"{log_prefix} Ping-pong limit ({PING_PONG_LIMIT}) exceeded for ConvID {conversation.id}. "
            "Tripping circuit breaker."
        )
        # Mudar o status da conversa para intervenção humana
        conversation.status = ConversationStatusEnum.PENDING
        db.add(conversation)
        await db.commit()  # Commita a mudança de status imediatamente
        raise PingPongLimitExceeded(
            f"Conversation {conversation.id} requires human intervention due to ping-pong limit."
        )
