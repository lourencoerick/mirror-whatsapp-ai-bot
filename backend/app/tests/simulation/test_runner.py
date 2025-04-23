# backend/app/tests/simulation/test_runner.py

import pytest
import uuid
import asyncio
import pytest_asyncio
from unittest import mock
from typing import List, Tuple, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone
from loguru import logger

# Importar o que será testado e dependências
from app.simulation import runner as simulation_runner  # Importa o módulo runner
from app.simulation.schemas.persona_definition import PersonaDefinition, InfoRequest
from app.simulation.schemas.persona_state import PersonaState, ExtractedFact
from app.models.simulation.simulation import (
    Simulation,
    SimulationStatusEnum,
    SimulationOutcomeEnum,
)
from app.models.simulation.simulation_message import SimulationMessageRoleEnum
from app.models.simulation.simulation_event import SimulationEventTypeEnum
from app.models.company_profile import CompanyProfile
from app.models.message import Message  # Para mock de poll_for_ai_response
from scripts.simulation.setup_simulation_entities import setup_entities

# Marcar testes como asyncio
pytestmark = pytest.mark.asyncio

# --- Mocks e Fixtures ---


# Mock para os módulos que o runner importa
# Usamos patch.object para mockar funções dentro dos módulos importados pelo runner


@pytest_asyncio.fixture(scope="function")
async def ensure_simulation_entities(db_session: AsyncSession):
    """
    Fixture that runs the simulation entity setup logic using the test session.
    """
    logger.info("Fixture: Ensuring simulation entities exist...")
    try:
        # Chama a função passando a sessão do teste
        await setup_entities(db=db_session)
        # Flush para garantir que os objetos estão na sessão antes do teste rodar
        await db_session.flush()
        logger.info("Fixture: Simulation entities setup flushed within test session.")
        # O commit final será feito pela fixture db_session
        yield  # O teste roda aqui
    except Exception as e:
        logger.error(f"Fixture: Error during simulation entity setup: {e}")
        # Rollback é feito automaticamente pela fixture db_session em caso de erro
        raise


@pytest.fixture
def mock_profile_repo():
    with mock.patch(
        "app.simulation.runner.profile_repo", new_callable=mock.AsyncMock
    ) as mocked:
        # Configurar retorno padrão para get_profile_by_account_id
        mocked.get_profile_by_account_id.return_value = CompanyProfile(
            id=uuid.uuid4(),
            account_id=simulation_runner.SIMULATION_ACCOUNT_ID,
            company_name="Mock Company",
            business_description="Desc",
            ai_objective="Obj",
            language="pt-BR",
            sales_tone="tone",
            fallback_contact_info="fallback",  # Adicionar campos obrigatórios
            # ... outros campos necessários ...
        )
        yield mocked


@pytest.fixture
def mock_persona_loader():
    with mock.patch(
        "app.simulation.runner.persona_loader", new_callable=mock.AsyncMock
    ) as mocked:
        # Configurar retorno padrão para load_persona
        mocked.load_persona.return_value = PersonaDefinition(
            persona_id="mock_persona",
            simulation_contact_identifier="mock_id",
            description="Mock Desc",
            initial_message="Mock Init",
            objective="Mock Obj",
            information_needed=[InfoRequest(entity="E1", attribute="A1")],
            info_attribute_to_question_template={"A1": "Question for {entity}?"},
            success_criteria=["state:all_info_extracted"],
            failure_criteria=[],
        )
        yield mocked


@pytest.fixture
def mock_simulation_repo():
    with mock.patch(
        "app.simulation.runner.simulation_repo", new_callable=mock.AsyncMock
    ) as mocked:
        # Configurar create_simulation para retornar um objeto Simulation mockado ou real
        mock_sim = Simulation(
            id=uuid.uuid4(), status=SimulationStatusEnum.RUNNING
        )  # Objeto simples
        mocked.create_simulation.return_value = mock_sim
        # update_simulation pode não precisar de retorno específico, só verificar chamada
        yield mocked


@pytest.fixture
def mock_simulation_message_repo():
    with mock.patch(
        "app.simulation.runner.simulation_message_repo", new_callable=mock.AsyncMock
    ) as mocked:
        yield mocked  # Só precisamos verificar chamadas


@pytest.fixture
def mock_simulation_event_repo():
    with mock.patch(
        "app.simulation.runner.simulation_event_repo", new_callable=mock.AsyncMock
    ) as mocked:
        yield mocked  # Só precisamos verificar chamadas


@pytest.fixture
def mock_webhook_utils():
    with mock.patch(
        "app.simulation.runner.webhook_utils", new_callable=mock.Mock
    ) as mocked:
        # Mockar funções síncronas e assíncronas dentro do módulo utils
        mocked.create_message_payload = mock.Mock(return_value={"payload": "data"})
        mocked.send_message_to_webhook = mock.AsyncMock(
            return_value={"conversation_id": str(uuid.uuid4())}
        )  # Retorna um conversation_id mockado
        mocked.poll_for_ai_response = mock.AsyncMock()  # Será configurado por teste
        mocked.check_explicit_failure_criteria = mock.Mock(
            return_value=None
        )  # Default: não falha
        yield mocked


@pytest.fixture
def mock_persona_logic():
    with mock.patch(
        "app.simulation.runner.persona_logic", new_callable=mock.Mock
    ) as mocked:
        # Mockar a função async get_next_persona_action
        mocked.get_next_persona_action = mock.AsyncMock()  # Será configurado por teste
        yield mocked


@pytest.fixture  # Fixture para reset (mock síncrono pois é chamado antes do await principal)
def mock_cleanup_utils():
    with mock.patch(
        "app.simulation.runner.reset_simulation_conversation",
        new_callable=mock.AsyncMock,
    ) as mocked:
        yield mocked


# --- Teste do Caminho Feliz ---


async def test_run_single_simulation_success_info_obtained(
    ensure_simulation_entities,
    mock_profile_repo,
    mock_persona_loader,
    mock_simulation_repo,
    mock_simulation_message_repo,
    mock_simulation_event_repo,
    mock_webhook_utils,
    mock_persona_logic,
    mock_cleanup_utils,  # Adicionar mock do reset
):
    """
    Tests the happy path where the persona obtains all needed information.
    """
    # --- Arrange ---
    persona_id_to_run = "mock_persona"
    test_conversation_id = uuid.uuid4()  # ID da conversa que esperamos ser usado
    mock_webhook_utils.send_message_to_webhook.return_value = {
        "conversation_id": str(test_conversation_id)
    }  # Garante que o ID correto é retornado

    # Configurar Mocks para o fluxo:
    # 1. AI responde com a informação A1
    ai_response_1 = Message(
        id=uuid.uuid4(),
        content="Info about A1 for E1",
        direction="out",
        conversation_id=test_conversation_id,
        created_at=datetime.now(timezone.utc),
    )
    mock_webhook_utils.poll_for_ai_response.return_value = ai_response_1

    # 2. Persona Logic extrai o fato A1 e termina (pois era a única info necessária)
    state_after_a1 = PersonaState(
        extracted_facts=[
            ExtractedFact(entity="E1", attribute="A1", value="Info about A1 for E1")
        ]
    )
    mock_persona_logic.get_next_persona_action.return_value = (
        None,  # No next message
        state_after_a1,  # State updated
        True,  # Terminate = True
        SimulationOutcomeEnum.INFO_OBTAINED,  # Outcome
    )

    # --- Action ---
    await simulation_runner.run_single_simulation(
        persona_id=persona_id_to_run, reset_conversation=False
    )

    # --- Assertions ---
    # Verificar chamadas principais
    mock_profile_repo.get_profile_by_account_id.assert_awaited_once()
    mock_persona_loader.load_persona.assert_awaited_once_with(persona_id_to_run)
    mock_simulation_repo.create_simulation.assert_awaited_once()
    # Verifica envio da mensagem inicial
    mock_webhook_utils.send_message_to_webhook.assert_awaited_once()
    # Verifica polling pela resposta da IA (deve ser chamado uma vez neste cenário)
    mock_webhook_utils.poll_for_ai_response.assert_awaited_once()
    # Verifica chamada à lógica da persona
    mock_persona_logic.get_next_persona_action.assert_awaited_once()
    # Verifica se o reset NÃO foi chamado
    mock_cleanup_utils.assert_not_awaited()

    # Verificar logs de mensagens (deve ter USER inicial e ASSISTANT da IA)
    assert mock_simulation_message_repo.create_message.await_count == 2
    mock_simulation_message_repo.create_message.assert_any_await(
        mock.ANY,  # db session
        simulation_id=mock.ANY,
        turn=1,
        role=SimulationMessageRoleEnum.USER,
        content="Mock Init",
    )
    mock_simulation_message_repo.create_message.assert_any_await(
        mock.ANY,  # db session
        simulation_id=mock.ANY,
        turn=1,
        role=SimulationMessageRoleEnum.ASSISTANT,
        content="Info about A1 for E1",
    )

    # Verificar logs de eventos chave
    event_calls = mock_simulation_event_repo.create_event.await_args_list
    event_types_logged = [call.kwargs["event_type"] for call in event_calls]
    assert SimulationEventTypeEnum.SIMULATION_START in event_types_logged
    assert (
        SimulationEventTypeEnum.TURN_START in event_types_logged
    )  # Pelo menos Turno 1
    assert SimulationEventTypeEnum.USER_MESSAGE_SENT in event_types_logged
    assert SimulationEventTypeEnum.AI_RESPONSE_RECEIVED in event_types_logged
    assert (
        SimulationEventTypeEnum.PERSONA_OBJECTIVE_MET in event_types_logged
    )  # Sucesso
    assert SimulationEventTypeEnum.SIMULATION_END in event_types_logged
    assert (
        SimulationEventTypeEnum.PERSONA_GAVE_UP not in event_types_logged
    )  # Não deve ter desistido

    # Verificar atualização final da simulação
    mock_simulation_repo.update_simulation.assert_awaited_once()
    # Pegar os argumentos da chamada de update
    update_call_args = mock_simulation_repo.update_simulation.await_args[
        0
    ]  # Pega args posicionais
    update_call_kwargs = mock_simulation_repo.update_simulation.await_args[
        1
    ]  # Pega kwargs
    final_update_data = update_call_kwargs.get("update_data", {})

    assert final_update_data.get("status") == SimulationStatusEnum.COMPLETED
    assert final_update_data.get("outcome") == SimulationOutcomeEnum.INFO_OBTAINED
    assert final_update_data.get("turn_count") == 1  # Terminou no primeiro turno da IA
    assert final_update_data.get("error_message") is None
    assert final_update_data.get("fallback_used") is False


# TODO: Adicionar mais testes para:
# - Múltiplos turnos antes de sucesso
# - Falha por timeout no poll_for_ai_response
# - Falha por critério explícito (turn_count, fallback_detected)
# - Falha por erro na chamada do webhook
# - Falha por erro na chamada do trustcall/LLM
# - Teste com a flag reset_conversation=True (verificar chamada a mock_cleanup_utils)
