# backend/app/tests/simulation/utils/test_webhook.py

import pytest
import uuid
import time
import json  # Importar json
from datetime import datetime, timezone, timedelta
from unittest import mock
from typing import List, Optional
import logging

import httpx  # Para mockar respostas HTTP
from sqlalchemy.ext.asyncio import AsyncSession

# Importar o módulo a ser testado (com novo nome)
from app.simulation.utils import webhook as webhook_utils

# Importar schemas, modelos, enums e configs necessários
from app.api.schemas.webhooks.evolution import EvolutionWebhookPayload
from app.models.message import Message
from app.simulation.schemas.persona_definition import PersonaDefinition, InfoRequest
from app.models.simulation.simulation import SimulationOutcomeEnum
from app.models.simulation.simulation_event import SimulationEventTypeEnum
from app.simulation.config import (
    SIMULATION_ACCOUNT_ID,
    SIMULATION_INBOX_ID,
    SIMULATION_CONTACT_ID,  # Ainda usado para o 'destination' no payload
    SIMULATION_CHANNEL_ID,
    POLL_INTERVAL_SECONDS,
    MAX_POLL_ATTEMPTS,
)

# Marcar testes como asyncio onde necessário
pytestmark = pytest.mark.asyncio

# --- Testes para create_message_payload ---


def test_create_message_payload_structure():
    """Verifica a estrutura básica e o uso do identifier no payload gerado."""
    message_text = "Test message"
    identifier = "5511987654321"
    payload = webhook_utils.create_message_payload(
        message_text=message_text, identifier=identifier
    )

    assert isinstance(payload, dict)
    assert payload["event"] == "messages.upsert"
    assert payload["instance"] == str(SIMULATION_CHANNEL_ID)
    assert "data" in payload
    data = payload["data"]
    assert data["key"]["remoteJid"] == f"{identifier}@simulated.whatsapp.net"
    assert data["key"]["fromMe"] is False
    assert data["message"]["conversation"] == message_text
    assert data["instanceId"] == str(SIMULATION_CHANNEL_ID)
    # O destination ainda usa os IDs fixos, o que parece correto para roteamento interno
    assert payload["destination"] == f"{SIMULATION_CONTACT_ID}@{SIMULATION_INBOX_ID}"


def test_create_message_payload_timestamp():
    """Verifica se o timestamp gerado é razoável."""
    message_text = "Timestamp test"
    identifier = "5511912345678"
    payload = webhook_utils.create_message_payload(message_text, identifier=identifier)
    timestamp = payload["data"]["messageTimestamp"]
    assert isinstance(timestamp, int)
    # Verifica se está próximo do tempo atual (margem de 60 segundos)
    assert abs(time.time() - timestamp) < 60


# --- Testes para send_message_to_webhook ---


@pytest.fixture
def mock_httpx_client():
    """Fixture para mockar httpx.AsyncClient."""
    # --- MODIFICADO: Corrigido o path do mock ---
    with mock.patch(
        "app.simulation.utils.webhook.httpx.AsyncClient"
    ) as mock_client_class:
        # ------------------------------------------
        mock_client = mock.AsyncMock()
        mock_response = mock.Mock(spec=httpx.Response)
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        yield mock_client, mock_response


async def test_send_message_to_webhook_success(mock_httpx_client):
    """Testa envio bem-sucedido ao webhook (status 200, JSON válido)."""
    mock_client, mock_response = mock_httpx_client
    expected_response_json = {"status": "ok", "conversation_id": str(uuid.uuid4())}
    mock_response.status_code = 200
    mock_response.json.return_value = expected_response_json
    mock_response.raise_for_status = mock.Mock()

    payload = {"test": "data"}
    response = await webhook_utils.send_message_to_webhook(payload)

    assert response == expected_response_json
    mock_client.post.assert_awaited_once()


async def test_send_message_to_webhook_http_error(mock_httpx_client):
    """Testa falha no envio ao webhook devido a erro HTTP (e.g., 4xx, 5xx)."""
    mock_client, mock_response = mock_httpx_client
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found", request=mock.Mock(), response=mock_response
    )

    payload = {"test": "data"}
    response = await webhook_utils.send_message_to_webhook(payload)

    assert response is None
    mock_client.post.assert_awaited_once()


async def test_send_message_to_webhook_request_error(mock_httpx_client):
    """Testa falha no envio ao webhook devido a erro de requisição (e.g., conexão)."""
    mock_client, mock_response = mock_httpx_client
    mock_client.post.side_effect = httpx.RequestError(
        "Connection failed", request=mock.Mock()
    )

    payload = {"test": "data"}
    response = await webhook_utils.send_message_to_webhook(payload)

    assert response is None
    mock_client.post.assert_awaited_once()


async def test_send_message_to_webhook_non_json_response(mock_httpx_client):
    """Testa envio bem-sucedido (status 200) mas com resposta não-JSON."""
    mock_client, mock_response = mock_httpx_client
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    mock_response.raise_for_status = mock.Mock()

    payload = {"test": "data"}
    response = await webhook_utils.send_message_to_webhook(payload)

    assert response == {"status": "success", "conversation_id": None}
    mock_client.post.assert_awaited_once()


# --- Testes para poll_for_ai_response ---


@pytest.fixture
def mock_db_execute():
    """Fixture para mockar db.execute."""
    # --- MODIFICADO: Corrigido o path do mock ---
    # Mockar dentro da AsyncSession que é usada no utilitário
    with mock.patch(
        "sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=mock.AsyncMock
    ) as mock_exec:
        # ------------------------------------------
        yield mock_exec


# Assume que db_session é uma fixture válida do conftest.py
async def test_poll_for_ai_response_found(mock_db_execute, db_session: AsyncSession):
    """Testa encontrar a resposta da IA na primeira tentativa."""
    conversation_id = uuid.uuid4()
    last_ts = datetime.now(timezone.utc) - timedelta(seconds=10)
    ai_message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        direction="out",
        content="AI Reply",
        created_at=datetime.now(timezone.utc),
    )
    mock_result = mock.Mock()
    mock_result.scalars.return_value.first.return_value = ai_message
    mock_db_execute.return_value = mock_result

    with mock.patch("asyncio.sleep", return_value=None):
        found_message = await webhook_utils.poll_for_ai_response(
            db_session, conversation_id, last_ts
        )

    assert found_message is not None
    assert found_message.id == ai_message.id
    mock_db_execute.assert_awaited_once()


async def test_poll_for_ai_response_timeout(mock_db_execute, db_session: AsyncSession):
    """Testa o timeout quando a resposta da IA nunca é encontrada."""
    conversation_id = uuid.uuid4()
    last_ts = datetime.now(timezone.utc)
    mock_result = mock.Mock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db_execute.return_value = mock_result

    start_time = time.time()
    with mock.patch("asyncio.sleep", return_value=None) as mock_sleep:
        found_message = await webhook_utils.poll_for_ai_response(
            db_session, conversation_id, last_ts
        )
    end_time = time.time()

    assert found_message is None
    assert mock_db_execute.await_count == MAX_POLL_ATTEMPTS
    assert mock_sleep.await_count == MAX_POLL_ATTEMPTS
    assert (end_time - start_time) < 0.1  # Teste deve ser rápido


async def test_poll_for_ai_response_found_after_delay(
    mock_db_execute, db_session: AsyncSession
):
    """Testa encontrar a resposta após algumas tentativas."""
    conversation_id = uuid.uuid4()
    last_ts = datetime.now(timezone.utc) - timedelta(seconds=10)
    ai_message = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        direction="out",
        content="Delayed Reply",
        created_at=datetime.now(timezone.utc),
    )
    mock_result_none = mock.Mock()
    mock_result_none.scalars.return_value.first.return_value = None
    mock_result_found = mock.Mock()
    mock_result_found.scalars.return_value.first.return_value = ai_message
    mock_db_execute.side_effect = [
        mock_result_none,
        mock_result_none,
        mock_result_found,
    ]

    with mock.patch("asyncio.sleep", return_value=None):
        found_message = await webhook_utils.poll_for_ai_response(
            db_session, conversation_id, last_ts
        )

    assert found_message is not None
    assert found_message.id == ai_message.id
    assert mock_db_execute.await_count == 3


# --- Testes para check_explicit_failure_criteria ---


@pytest.fixture
def persona_for_failure_check() -> PersonaDefinition:
    from app.simulation.schemas.persona_definition import (
        PersonaDefinition,
    )  # Import local

    return PersonaDefinition(
        persona_id="failure_checker",
        simulation_contact_identifier="x",
        description="x",
        initial_message="x",
        objective="x",
        information_needed=[],
        info_attribute_to_question_template={},
        success_criteria=[],
        failure_criteria=[],
    )


def test_check_failure_turn_count_met(persona_for_failure_check):
    """Testa se o critério de turn_count é detectado."""
    persona = persona_for_failure_check
    persona.failure_criteria = ["turn_count > 5"]
    events = []
    assert (
        webhook_utils.check_explicit_failure_criteria(persona, 6, events)
        == SimulationOutcomeEnum.TURN_LIMIT_REACHED
    )
    assert webhook_utils.check_explicit_failure_criteria(persona, 5, events) is None


def test_check_failure_event_met(persona_for_failure_check):
    """Testa se o critério de evento é detectado."""
    persona = persona_for_failure_check
    persona.failure_criteria = ["event:ai_fallback_detected"]
    events_with_fallback = [SimulationEventTypeEnum.AI_FALLBACK_DETECTED]
    events_without_fallback = [SimulationEventTypeEnum.SIMULATION_START]
    assert (
        webhook_utils.check_explicit_failure_criteria(persona, 3, events_with_fallback)
        == SimulationOutcomeEnum.AI_USED_FALLBACK
    )
    assert (
        webhook_utils.check_explicit_failure_criteria(
            persona, 3, events_without_fallback
        )
        is None
    )


def test_check_failure_multiple_criteria(persona_for_failure_check):
    """Testa múltiplos critérios de falha."""
    persona = persona_for_failure_check
    persona.failure_criteria = ["turn_count > 3", "event:simulation_engine_error"]
    events_with_error = [SimulationEventTypeEnum.SIMULATION_ENGINE_ERROR]
    assert (
        webhook_utils.check_explicit_failure_criteria(persona, 4, [])
        == SimulationOutcomeEnum.TURN_LIMIT_REACHED
    )
    assert (
        webhook_utils.check_explicit_failure_criteria(persona, 2, events_with_error)
        == SimulationOutcomeEnum.SIMULATION_ERROR
    )
    assert webhook_utils.check_explicit_failure_criteria(persona, 3, []) is None


def test_check_failure_no_criteria_met(persona_for_failure_check):
    """Testa quando nenhum critério de falha é atendido."""
    persona = persona_for_failure_check
    persona.failure_criteria = ["turn_count > 5", "event:ai_fallback_detected"]
    events = [SimulationEventTypeEnum.SIMULATION_START]
    assert webhook_utils.check_explicit_failure_criteria(persona, 4, events) is None


def test_check_failure_invalid_criteria(persona_for_failure_check, caplog):
    """
    Testa se critérios completamente inválidos ou não reconhecidos são ignorados
    e se os logs corretos são gerados.
    """
    persona = persona_for_failure_check
    persona.failure_criteria = [
        "turn_count>5",  # Formato válido agora, não deve gerar warning de formato
        "event:invalid_event_type",  # Deve logar erro
        "random_string",  # Deve logar warning de formato não reconhecido
    ]
    events = []

    caplog.clear()
    caplog.set_level(logging.WARNING)  # Captura WARNING e ERROR

    # Action
    assert webhook_utils.check_explicit_failure_criteria(persona, 4, events) is None

    # Verificar logs individuais
    log_messages = [record.message for record in caplog.records]
    log_levels = [record.levelname for record in caplog.records]
    # print(f"\nCaptured Logs:\n{caplog.text}") # Descomente para debugar

    # Verifica o erro do evento inválido
    assert any(
        "Invalid event type in failure criterion: invalid_event_type" in msg
        for msg in log_messages
    )
    assert "ERROR" in log_levels  # Garante que foi logado como erro

    # --- REMOVIDO: Asserção para warning de turn_count>5 ---
    # assert any("Ignoring unrecognized failure criterion format: turn_count>5" in msg for msg in log_messages)
    # -------------------------------------------------------

    # Verifica o aviso para o formato não reconhecido "random_string"
    assert any(
        "Ignoring unrecognized failure criterion format: random_string" in msg
        for msg in log_messages
    )
    assert "WARNING" in log_levels  # Garante que foi logado como aviso

    # Garante que o log de erro do turn_count (que não deve ocorrer aqui) NÃO está presente
    assert not any(
        "Invalid number found in turn_count criterion" in msg for msg in log_messages
    )

    # --- Caso 2 (turn_count válido sem espaço) ---
    caplog.clear()
    persona.failure_criteria = ["turn_count>5", "event:some_other_event"]
    assert (
        webhook_utils.check_explicit_failure_criteria(persona, 6, events)
        == SimulationOutcomeEnum.TURN_LIMIT_REACHED
    )
    # Verifica o log de aviso correto para este caso
    assert any(
        "Failure criterion met: Turn count 6 exceeded limit 5" in record.message
        for record in caplog.records  # Iterar sobre records, mas checar record.message
    )
    assert "WARNING" in [
        rec.levelname for rec in caplog.records
    ]  # Garante que foi logado como aviso
