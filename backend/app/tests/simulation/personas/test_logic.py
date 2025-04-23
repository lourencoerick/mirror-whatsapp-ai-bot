# backend/app/tests/simulation/personas/test_logic.py

import pytest
from unittest import mock
from uuid import UUID
from typing import List, Optional, Tuple

# Importar o que será testado e dependências
from app.simulation.personas import logic as persona_logic
from app.simulation.schemas.persona_definition import PersonaDefinition, InfoRequest
from app.simulation.schemas.persona_state import PersonaState, ExtractedFact
from app.models.simulation.simulation import SimulationOutcomeEnum

# Marcar testes como asyncio pois a função é async
pytestmark = pytest.mark.asyncio

# --- Fixtures ---


@pytest.fixture
def sample_persona() -> PersonaDefinition:
    """Persona buscando preço e tamanho do Bolo de Cenoura."""
    return PersonaDefinition(
        persona_id="bolo_seeker",
        simulation_contact_identifier="5511955554444",
        description="Busca info de bolo",
        initial_message="?",
        objective="Obter preço e tamanho do Bolo de Cenoura",
        information_needed=[
            InfoRequest(entity="Bolo de Cenoura", attribute="price"),
            InfoRequest(entity="Bolo de Cenoura", attribute="size"),
        ],
        info_attribute_to_question_template={
            "price": "Qual o preço do {entity}?",
            "size": "Qual o tamanho do {entity}?",
        },
        success_criteria=["state:all_info_extracted"],
        failure_criteria=["event:AI_FALLBACK_DETECTED"],
    )


@pytest.fixture
def initial_persona_state() -> PersonaState:
    """Estado inicial da persona, sem fatos."""
    return PersonaState(extracted_facts=[])


@pytest.fixture
def state_with_price() -> PersonaState:
    """Estado da persona que já sabe o preço."""
    return PersonaState(
        extracted_facts=[
            ExtractedFact(entity="Bolo de Cenoura", attribute="price", value="R$ 30,00")
        ]
    )


# --- Test Cases ---


@mock.patch(
    "app.simulation.personas.logic.fact_extractor", new_callable=mock.AsyncMock
)  # Mock o extrator no módulo logic
async def test_get_next_action_extracts_price(
    mock_extractor,
    sample_persona: PersonaDefinition,
    initial_persona_state: PersonaState,
):
    """
    Testa se a persona pede o tamanho após a IA responder o preço.
    """
    # Arrange: Configura o mock do trustcall/LLM para retornar o fato 'price'
    ai_response = "O bolo de cenoura custa R$ 30,00."
    mock_extractor.ainvoke.return_value = {
        "responses": [
            ExtractedFact(entity="Bolo de Cenoura", attribute="price", value="R$ 30,00")
        ]
    }

    # Action
    next_msg, updated_state, terminate, outcome = (
        await persona_logic.get_next_persona_action(
            persona=sample_persona,
            ai_response_text=ai_response,
            current_state=initial_persona_state,
        )
    )

    # Assertions
    mock_extractor.ainvoke.assert_awaited_once()  # Verifica se o extrator foi chamado
    assert terminate is False
    assert outcome is None
    assert updated_state.has_fact("Bolo de Cenoura", "price") is True
    assert updated_state.get_fact("Bolo de Cenoura", "price") == "R$ 30,00"
    assert updated_state.has_fact("Bolo de Cenoura", "size") is False
    # Verifica se a próxima pergunta é sobre o tamanho (que ainda falta)
    assert next_msg == sample_persona.info_attribute_to_question_template[
        "size"
    ].format(entity="Bolo de Cenoura")


@mock.patch("app.simulation.personas.logic.fact_extractor", new_callable=mock.AsyncMock)
async def test_get_next_action_extracts_size_when_price_known(
    mock_extractor, sample_persona: PersonaDefinition, state_with_price: PersonaState
):
    """
    Testa se a persona termina com sucesso após a IA responder o tamanho (última info).
    """
    # Arrange: Persona já sabe o preço, IA responde o tamanho
    ai_response = "Ele serve 10 pessoas."
    mock_extractor.ainvoke.return_value = {
        "responses": [
            ExtractedFact(
                entity="Bolo de Cenoura", attribute="size", value="Serve 10 pessoas"
            )
        ]
    }

    # Action
    next_msg, updated_state, terminate, outcome = (
        await persona_logic.get_next_persona_action(
            persona=sample_persona,
            ai_response_text=ai_response,
            current_state=state_with_price,  # Começa com o estado que já tem o preço
        )
    )

    # Assertions
    mock_extractor.ainvoke.assert_awaited_once()
    assert (
        updated_state.has_fact("Bolo de Cenoura", "price") is True
    )  # Preço continua lá
    assert (
        updated_state.has_fact("Bolo de Cenoura", "size") is True
    )  # Tamanho foi adicionado
    # Verifica se terminou com sucesso pois obteve toda a informação
    assert terminate is True
    assert outcome == SimulationOutcomeEnum.INFO_OBTAINED
    assert next_msg is None  # Não deve haver próxima mensagem


@mock.patch("app.simulation.personas.logic.fact_extractor", new_callable=mock.AsyncMock)
async def test_get_next_action_extracts_multiple_facts(
    mock_extractor,
    sample_persona: PersonaDefinition,
    initial_persona_state: PersonaState,
):
    """
    Testa se a persona termina com sucesso se a IA responde tudo de uma vez.
    """
    # Arrange: IA responde preço E tamanho
    ai_response = "O bolo de cenoura custa R$ 30,00 e serve 10 pessoas."
    mock_extractor.ainvoke.return_value = {
        "responses": [
            ExtractedFact(
                entity="Bolo de Cenoura", attribute="price", value="R$ 30,00"
            ),
            ExtractedFact(
                entity="Bolo de Cenoura", attribute="size", value="Serve 10 pessoas"
            ),
        ]
    }

    # Action
    next_msg, updated_state, terminate, outcome = (
        await persona_logic.get_next_persona_action(
            persona=sample_persona,
            ai_response_text=ai_response,
            current_state=initial_persona_state,
        )
    )

    # Assertions
    mock_extractor.ainvoke.assert_awaited_once()
    assert updated_state.has_fact("Bolo de Cenoura", "price") is True
    assert updated_state.has_fact("Bolo de Cenoura", "size") is True
    # Verifica se terminou com sucesso
    assert terminate is True
    assert outcome == SimulationOutcomeEnum.INFO_OBTAINED
    assert next_msg is None


@mock.patch("app.simulation.personas.logic.fact_extractor", new_callable=mock.AsyncMock)
async def test_get_next_action_no_facts_extracted(
    mock_extractor,
    sample_persona: PersonaDefinition,
    initial_persona_state: PersonaState,
):
    """
    Testa se a persona repete a primeira pergunta se a IA não der info útil.
    """
    # Arrange: Resposta genérica da IA, mock retorna lista vazia
    ai_response = "Olá! Como posso ajudar?"
    mock_extractor.ainvoke.return_value = {"responses": []}

    # Action
    next_msg, updated_state, terminate, outcome = (
        await persona_logic.get_next_persona_action(
            persona=sample_persona,
            ai_response_text=ai_response,
            current_state=initial_persona_state,
        )
    )

    # Assertions
    mock_extractor.ainvoke.assert_awaited_once()
    assert terminate is False
    assert outcome is None
    assert not updated_state.extracted_facts  # Nenhum fato adicionado
    # Verifica se pergunta sobre o primeiro item necessário (preço)
    assert next_msg == sample_persona.info_attribute_to_question_template[
        "price"
    ].format(entity="Bolo de Cenoura")


@mock.patch("app.simulation.personas.logic.fact_extractor", new_callable=mock.AsyncMock)
async def test_get_next_action_trustcall_fails(
    mock_extractor,
    sample_persona: PersonaDefinition,
    initial_persona_state: PersonaState,
):
    """
    Testa se a persona continua com estado antigo se trustcall falhar.
    """
    # Arrange: Mock levanta exceção
    ai_response = "O preço é R$ 30,00."
    mock_extractor.ainvoke.side_effect = Exception("Simulated LLM API error")

    # Action
    next_msg, updated_state, terminate, outcome = (
        await persona_logic.get_next_persona_action(
            persona=sample_persona,
            ai_response_text=ai_response,
            current_state=initial_persona_state,
        )
    )

    # Assertions
    mock_extractor.ainvoke.assert_awaited_once()
    assert (
        terminate is False
    )  # Não deve terminar por erro do extrator (continua tentando)
    assert outcome is None
    assert updated_state == initial_persona_state  # Estado não deve mudar
    # Pergunta sobre o primeiro item necessário (preço), pois a extração falhou
    assert next_msg == sample_persona.info_attribute_to_question_template[
        "price"
    ].format(entity="Bolo de Cenoura")


# TODO: Adicionar testes para verificar a lógica de success_criteria e failure_criteria
# quando eles não são o padrão "state:all_info_extracted".
