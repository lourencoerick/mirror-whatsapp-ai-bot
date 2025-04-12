# tests/api/v1/test_conversations.py

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from app.models.conversation import Conversation, ConversationStatusEnum
from app.models.contact import Contact
from app.models.inbox import Inbox
from app.models.contact_inbox import ContactInbox
from app.api.schemas.conversation import (
    ConversationSearchResult,
)  # For response validation

from loguru import logger
from app.api.schemas.message import MessageResponse  # Para validar a resposta

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# --- Helper Fixture to Create a Conversation ---

API_V1_PREFIX = "/api/v1"


@pytest_asyncio.fixture(scope="function")
async def test_conversation(
    db_session: AsyncSession,
    test_account: "Account",  # Use forward reference if Account is defined later or type checking fails
    test_inbox: Inbox,
    test_contact: Contact,
) -> Conversation:
    """Creates a persisted test conversation."""
    # Ensure ContactInbox exists
    contact_inbox = await db_session.scalar(
        select(ContactInbox).filter_by(
            contact_id=test_contact.id, inbox_id=test_inbox.id
        )
    )
    if not contact_inbox:
        contact_inbox = ContactInbox(
            id=uuid4(),
            contact_id=test_contact.id,
            inbox_id=test_inbox.id,
            source_id=f"test-source-{uuid4().hex}",  # Example source_id
        )
        db_session.add(contact_inbox)
        await db_session.flush()
        await db_session.refresh(contact_inbox)

    # Create conversation with initial state
    conversation = Conversation(
        id=uuid4(),
        account_id=test_account.id,
        inbox_id=test_inbox.id,
        contact_inbox_id=contact_inbox.id,
        status=ConversationStatusEnum.PENDING,  # Start as PENDING
        unread_agent_count=5,  # Start with some unread messages
        additional_attributes={  # Add necessary attributes if needed by response schema
            "contact_name": test_contact.name,
            "phone_number": test_contact.phone_number,
            "profile_picture_url": test_contact.profile_picture_url,
            "last_message": {
                "id": str(uuid4()),
                "content": "Initial message",
                "sent_at": None,
            },  # Dummy last message if needed
        },
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.refresh(conversation)
    return conversation


# --- Test Function ---


# ... (fixture test_conversation) ...


async def test_create_outgoing_message_resets_unread_and_sets_active(
    client: AsyncClient,
    db_session: AsyncSession,
    test_conversation: Conversation,  # Usa a fixture que cria uma conversa PENDING com unread > 0
):
    """
    Test sending an outgoing message resets unread count and sets status to HUMAN_ACTIVE
    if it was PENDING.
    """
    conversation_id = test_conversation.id
    initial_unread_count = test_conversation.unread_agent_count
    initial_status = test_conversation.status
    assert initial_unread_count > 0
    assert initial_status == ConversationStatusEnum.PENDING

    # Define o payload da mensagem a ser enviada
    message_payload = {"content": "This is a reply from the agent."}

    # Faz a requisição POST para criar a mensagem
    response = await client.post(
        f"{API_V1_PREFIX}/conversations/{conversation_id}/messages",
        json=message_payload,
    )

    # 1. Verifica o status code da resposta
    assert response.status_code == 201  # 201 Created

    # 2. Verifica o corpo da resposta (contém a mensagem criada)
    response_data = response.json()
    # Valida a estrutura (opcional mas recomendado)
    # parsed_response = MessageResponse(**response_data)
    logger.info(response_data)
    # assert response_data["conversation_id"] == str(conversation_id)
    assert response_data["content"] == message_payload["content"]
    assert response_data["direction"] == "out"
    created_message_id = response_data["id"]  # Guarda o ID para verificar o snapshot

    logger.info(
        f"Message ID after Creating it: {created_message_id} and {test_conversation.additional_attributes.get('last_message', {}).get('id')}"
    )
    # 3. Verifica as mudanças na conversa no banco de dados
    await db_session.refresh(
        test_conversation
    )  # Atualiza o estado do objeto conversation
    assert (
        test_conversation.status == ConversationStatusEnum.HUMAN_ACTIVE
    )  # Status deve mudar
    assert test_conversation.unread_agent_count == 0  # Contador deve ser zerado
    logger.info(
        f"Message ID after Creating it: {created_message_id} and {test_conversation.additional_attributes.get('last_message', {}).get('id')}"
    )
    # 4. (Opcional) Verifica se o last_message_snapshot foi atualizado
    #    A implementação exata depende de como 'update_last_message_snapshot' funciona.
    #    Se ele atualiza um campo JSON 'additional_attributes':
    assert "last_message" in test_conversation.additional_attributes
    last_msg_snapshot = test_conversation.additional_attributes.get("last_message", {})
    assert last_msg_snapshot.get("id") == created_message_id
    assert last_msg_snapshot.get("content") == message_payload["content"]
    #    Se ele atualiza um campo 'last_message_at':
    # assert test_conversation.last_message_at is not None
    # assert test_conversation.last_message_at > initial_timestamp # (se você guardar o timestamp inicial)

    # 5. Verifica se a mensagem foi realmente salva no banco (opcional, mas bom)
    from app.models.message import Message  # Import localmente ou no topo

    stmt = select(Message).where(Message.id == created_message_id)
    saved_message = await db_session.scalar(stmt)
    assert saved_message is not None
    assert saved_message.direction == "out"
    # assert saved_message.conversation_id == conversation_id
