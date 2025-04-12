# tests/consumers/test_message_consumer.py

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime, timezone

# Imports necessários do app
from app.models.conversation import Conversation, ConversationStatusEnum
from app.models.contact import Contact
from app.models.inbox import Inbox
from app.models.contact_inbox import ContactInbox
from app.models.message import Message
from app.workers.message_consumer import MessageConsumer  # Importa a classe
from app.api.schemas.message import MessageCreate  # Para criar o payload

# Mark all tests in this file as async
pytestmark = pytest.mark.asyncio

# --- Fixture para Conversa Fechada ---


@pytest_asyncio.fixture(scope="function")
async def test_closed_conversation(
    db_session: AsyncSession,
    test_account: "Account",
    test_inbox: Inbox,
    test_contact: Contact,
) -> Conversation:
    """Creates a persisted test conversation that is CLOSED and has 0 unread."""
    # Garante ContactInbox
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
            source_id=f"test-closed-source-{uuid4().hex}",
        )
        db_session.add(contact_inbox)
        await db_session.flush()
        await db_session.refresh(contact_inbox)

    # Cria a conversa FECHADA
    conversation = Conversation(
        id=uuid4(),
        account_id=test_account.id,
        inbox_id=test_inbox.id,
        contact_inbox_id=contact_inbox.id,
        status=ConversationStatusEnum.CLOSED,  # <<< Estado inicial CLOSED
        unread_agent_count=0,  # <<< Estado inicial 0
        additional_attributes={
            "contact_name": test_contact.name,
            "phone_number": test_contact.phone_number,
            "profile_picture_url": test_contact.profile_picture_url,
            "last_message": {  # Snapshot de uma mensagem anterior (opcional)
                "id": str(uuid4()),
                "content": "Previous message",
                "sent_at": None,
                "direction": "out",
                "content_type": "text",
            },
        },
        last_message_at=datetime.now(timezone.utc),  # Timestamp da última mensagem
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.refresh(conversation)
    return conversation


# --- Test Function ---


async def test_handle_incoming_message_reopens_closed_conversation(
    db_session: AsyncSession,
    test_closed_conversation: Conversation,  # Usa a nova fixture
    test_account: "Account",  # Precisa do account_id
    test_contact: Contact,  # Precisa do contact_id
):
    """
    Test that _handle_message correctly processes an incoming message
    for a closed conversation, reopening it and incrementing unread count.
    """
    # Arrange
    conversation = test_closed_conversation
    assert conversation.status == ConversationStatusEnum.CLOSED
    assert conversation.unread_agent_count == 0

    # Cria os dados da mensagem simulando o que viria da fila
    # Usa os IDs da conversa/inbox/contato existentes
    message_source_id = f"webhook-{uuid4().hex}"
    message_content = "Hello, I need help again!"
    message_timestamp = datetime.now(timezone.utc)

    message_data_dict = {
        "account_id": str(conversation.account_id),
        "inbox_id": str(conversation.inbox_id),
        "conversation_id": str(conversation.id),
        "contact_id": str(test_contact.id),  # Usa o ID do contato da fixture
        "source_id": message_source_id,  # ID único da mensagem externa
        "user_id": None,  # Mensagem do contato não tem user_id
        "direction": "in",  # <<< Mensagem de entrada
        "private": False,
        "status": "delivered",  # Status inicial da mensagem recebida
        "message_timestamp": message_timestamp.isoformat(),  # Envia como string ISO
        "content": message_content,
        "content_type": "text",
        "content_attributes": {"source": "whatsapp"},  # Exemplo
    }

    # Instancia o consumidor
    consumer = MessageConsumer()  # Não precisa das filas para testar _handle_message

    # Act
    # Chama o método diretamente com a sessão de teste e os dados
    await consumer._handle_message(db_session, message_data_dict)

    # Commit explícito para simular o fim da transação no loop 'run'
    await db_session.commit()

    # Assert
    # Atualiza o estado da conversa do banco de dados
    await db_session.refresh(conversation)

    # 1. Verifica o estado da conversa
    assert (
        conversation.status == ConversationStatusEnum.PENDING
    )  # <<< Deve reabrir para PENDING
    assert conversation.unread_agent_count == 1  # <<< Deve incrementar para 1

    # 2. Verifica o snapshot da última mensagem na conversa
    assert "last_message" in conversation.additional_attributes
    last_msg_snapshot = conversation.additional_attributes.get("last_message", {})
    assert last_msg_snapshot.get("content") == message_content
    assert last_msg_snapshot.get("direction") == "in"
    # O ID da mensagem no snapshot precisa ser verificado buscando a mensagem salva
    # assert conversation.last_message_at == message_timestamp # Compara timestamps

    # 3. Verifica se a mensagem foi salva corretamente no banco
    stmt = select(Message).where(
        Message.account_id == conversation.account_id,
        Message.source_id == message_source_id,
    )
    saved_message = await db_session.scalar(stmt)
    assert saved_message is not None
    assert saved_message.direction == "in"
    assert saved_message.content == message_content
    assert saved_message.conversation_id == conversation.id

    # 4. Verifica o ID no snapshot contra a mensagem salva
    assert last_msg_snapshot.get("id") == str(saved_message.id)


@pytest_asyncio.fixture(scope="function")
async def test_pending_conversation(
    db_session: AsyncSession,
    test_account: "Account",
    test_inbox: Inbox,
    test_contact: Contact,
) -> Conversation:
    """Creates a persisted test conversation that is PENDING and has 1 unread."""
    # Garante ContactInbox
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
            source_id=f"test-pending-source-{uuid4().hex}",
        )
        db_session.add(contact_inbox)
        await db_session.flush()
        await db_session.refresh(contact_inbox)

    # Cria a conversa PENDING com 1 não lida
    conversation = Conversation(
        id=uuid4(),
        account_id=test_account.id,
        inbox_id=test_inbox.id,
        contact_inbox_id=contact_inbox.id,
        status=ConversationStatusEnum.PENDING,  # <<< Estado inicial PENDING
        unread_agent_count=1,  # <<< Estado inicial 1
        additional_attributes={
            "contact_name": test_contact.name,
            "phone_number": test_contact.phone_number,
            "profile_picture_url": test_contact.profile_picture_url,
            "last_message": {
                "id": str(uuid4()),
                "content": "First message",
                "sent_at": None,
                "direction": "in",
                "content_type": "text",
            },
        },
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.refresh(conversation)
    return conversation


# --- Test Function ---


async def test_handle_incoming_message_increments_unread_for_open_conversation(
    db_session: AsyncSession,
    test_pending_conversation: Conversation,  # Usa a nova fixture
    test_account: "Account",
    test_contact: Contact,
):
    """
    Test that _handle_message correctly increments unread count for an already
    open (PENDING) conversation without changing its status.
    """
    # Arrange
    conversation = test_pending_conversation
    initial_status = conversation.status
    initial_unread_count = conversation.unread_agent_count
    assert initial_status == ConversationStatusEnum.PENDING
    assert initial_unread_count == 1  # Verifica estado inicial da fixture

    # Cria os dados da nova mensagem de entrada
    message_source_id = f"webhook-followup-{uuid4().hex}"
    message_content = "Just checking in again."
    message_timestamp = datetime.now(timezone.utc)

    message_data_dict = {
        "account_id": str(conversation.account_id),
        "inbox_id": str(conversation.inbox_id),
        "conversation_id": str(conversation.id),
        "contact_id": str(test_contact.id),
        "source_id": message_source_id,
        "user_id": None,
        "direction": "in",  # <<< Mensagem de entrada
        "private": False,
        "status": "delivered",
        "message_timestamp": message_timestamp.isoformat(),
        "content": message_content,
        "content_type": "text",
        "content_attributes": {"source": "whatsapp"},
    }

    # Instancia o consumidor
    consumer = MessageConsumer()

    # Act
    await consumer._handle_message(db_session, message_data_dict)
    await db_session.commit()  # Persiste as alterações

    # Assert
    await db_session.refresh(conversation)  # Atualiza o estado do banco

    # 1. Verifica o estado da conversa
    assert conversation.status == initial_status  # <<< Status NÃO deve mudar
    assert (
        conversation.unread_agent_count == initial_unread_count + 1
    )  # <<< Deve incrementar

    # 2. Verifica o snapshot
    assert "last_message" in conversation.additional_attributes
    last_msg_snapshot = conversation.additional_attributes.get("last_message", {})
    assert last_msg_snapshot.get("content") == message_content
    assert last_msg_snapshot.get("direction") == "in"
    # assert conversation.last_message_at == message_timestamp

    # 3. Verifica se a mensagem foi salva
    stmt = select(Message).where(
        Message.account_id == conversation.account_id,
        Message.source_id == message_source_id,
    )
    saved_message = await db_session.scalar(stmt)
    assert saved_message is not None
    assert saved_message.content == message_content
    assert saved_message.conversation_id == conversation.id

    # 4. Verifica ID do snapshot
    assert last_msg_snapshot.get("id") == str(saved_message.id)
