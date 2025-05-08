# tests/unit/test_knowledge_retriever.py

import pytest
from unittest.mock import (
    AsyncMock,
    patch,
    MagicMock,
    ANY,
)  # ANY para argumentos não específicos
from uuid import uuid4
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

# Importar a função a ser testada e definições/schemas
from app.services.new_agent.components.knowledge_retriever import (
    knowledge_retriever_node,
)
from app.services.new_agent.state_definition import (
    RichConversationState,
    AgentActionType,
    AgentActionDetails,
)

# Mock para KnowledgeChunk se o import real falhar no ambiente de teste
try:
    from app.models.knowledge_chunk import KnowledgeChunk
except ImportError:

    class KnowledgeChunk:  # Dummy
        def __init__(self, chunk_text: str, metadata_: Optional[Dict] = None):
            self.chunk_text = chunk_text
            self.metadata_ = metadata_


@pytest.fixture
def mock_db_session_factory():
    # 1. Mock da sessão que será retornada pelo __aenter__
    mock_session = AsyncMock(
        spec=AsyncSession
    )  # Adicionar spec=AsyncSession se disponível

    # 2. Mock do gerenciador de contexto assíncrono
    mock_context_manager = AsyncMock()
    # Configurar o __aenter__ para retornar a sessão mockada
    mock_context_manager.__aenter__.return_value = mock_session
    # __aexit__ pode retornar None ou um valor mockado se necessário
    mock_context_manager.__aexit__.return_value = None

    # 3. Mock da factory
    # Configurar a factory para retornar o GERENCIADOR DE CONTEXTO quando for chamada
    factory = MagicMock(return_value=mock_context_manager)

    # (Opcional) Adicionar um helper para acessar a sessão mockada nos testes
    factory._get_mock_session = lambda: mock_session

    return factory


# Fixture para estado base (pode ser importado de um conftest.py comum)
@pytest.fixture
def base_state_for_retriever() -> RichConversationState:
    """Provides a base RichConversationState for retriever tests."""
    state = RichConversationState(
        account_id=uuid4(),
        conversation_id=uuid4(),
        bot_agent_id=None,
        company_profile={},
        agent_config={},
        messages=[],
        current_user_input_text="",
        current_turn_number=1,
        current_agent_goal={"goal_type": "IDLE"},
        last_agent_action=None,
        user_interruptions_queue=[],
        customer_profile_dynamic={
            "identified_needs": [],
            "identified_pain_points": [],
            "identified_objections": [],
            "certainty_levels": {},
        },
        customer_question_log=[],
        current_turn_extracted_questions=[],
        active_proposal=None,
        closing_process_status="not_started",
        last_objection_handled_turn=None,
        retrieved_knowledge_for_next_action=None,
        last_agent_generation_text=None,
        conversation_summary_for_llm=None,
        last_interaction_timestamp=0.0,
        is_simulation=False,
        last_processing_error=None,
        disengagement_reason=None,
        user_input_analysis_result=None,
        # Campos que o retriever usa:
        next_agent_action_command=None,
        action_parameters={},
    )
    return state


# --- Testes ---


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.knowledge_retriever.get_embedding",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.knowledge_retriever.search_similar_chunks",
    new_callable=AsyncMock,
)
async def test_retriever_success_for_question(
    mock_search_chunks,
    mock_get_embedding,
    base_state_for_retriever,
    mock_db_session_factory,
):
    """Test successful retrieval for answering a direct question."""
    state = base_state_for_retriever
    question_text = "Qual a política de devolução?"
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": question_text}

    # Configurar mocks
    mock_embedding_vector = [0.1] * 10  # Vetor de embedding simulado
    mock_get_embedding.return_value = mock_embedding_vector

    mock_chunks = [
        KnowledgeChunk(
            chunk_text="Nossa política permite devoluções em 30 dias.",
            metadata_={"original_source": "faq.pdf", "page_number": 2},
        ),
        KnowledgeChunk(
            chunk_text="O produto deve estar sem uso.",
            metadata_={"original_source": "termos.txt"},
        ),
    ]
    mock_search_chunks.return_value = mock_chunks

    config = {"configurable": {"db_session_factory": mock_db_session_factory}}

    # Executar nó
    delta = await knowledge_retriever_node(state, config)

    # Verificar asserts
    mock_get_embedding.assert_called_once_with(question_text)
    mock_search_chunks.assert_called_once_with(
        db=ANY,  # Verificar se a sessão foi passada (ANY porque é um mock)
        account_id=state["account_id"],
        query_embedding=mock_embedding_vector,
        limit=ANY,  # Ou o valor default
        similarity_threshold=ANY,  # Ou o valor default
    )

    assert "retrieved_knowledge_for_next_action" in delta
    context = delta["retrieved_knowledge_for_next_action"]
    assert context is not None
    assert "Contexto Relevante Encontrado:" in context
    assert "Nossa política permite devoluções em 30 dias." in context
    assert "[Fonte: faq.pdf (Página: 2)]" in context
    assert "O produto deve estar sem uso." in context
    assert (
        "[Fonte: termos.txt ]" in context
    )  # Nota o espaço extra se page_number não existe
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.knowledge_retriever.get_embedding",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.knowledge_retriever.search_similar_chunks",
    new_callable=AsyncMock,
)
async def test_retriever_success_for_objection(
    mock_search_chunks,
    mock_get_embedding,
    base_state_for_retriever,
    mock_db_session_factory,
):
    """Test successful retrieval for handling an objection."""
    state = base_state_for_retriever
    objection_text = "É muito caro."
    state["next_agent_action_command"] = "GENERATE_REBUTTAL"
    state["action_parameters"] = {"objection_text_to_address": objection_text}

    mock_embedding_vector = [0.2] * 10
    mock_get_embedding.return_value = mock_embedding_vector
    mock_chunks = [KnowledgeChunk(chunk_text="Enfatize o ROI e o valor a longo prazo.")]
    mock_search_chunks.return_value = mock_chunks

    config = {"configurable": {"db_session_factory": mock_db_session_factory}}

    delta = await knowledge_retriever_node(state, config)

    expected_query = f"Como responder à objeção do cliente sobre: {objection_text}"
    mock_get_embedding.assert_called_once_with(expected_query)
    mock_search_chunks.assert_called_once()

    assert "retrieved_knowledge_for_next_action" in delta
    context = delta["retrieved_knowledge_for_next_action"]
    assert context is not None
    assert "Enfatize o ROI e o valor a longo prazo." in context
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.knowledge_retriever.get_embedding",
    new_callable=AsyncMock,
)
@patch(
    "app.services.new_agent.components.knowledge_retriever.search_similar_chunks",
    new_callable=AsyncMock,
)
async def test_retriever_no_chunks_found(
    mock_search_chunks,
    mock_get_embedding,
    base_state_for_retriever,
    mock_db_session_factory,
):
    """Test the case where no relevant chunks are found."""
    state = base_state_for_retriever
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {
        "question_to_answer_text": "Pergunta muito específica"
    }

    mock_get_embedding.return_value = [0.3] * 10
    mock_search_chunks.return_value = []  # Nenhum chunk encontrado

    config = {"configurable": {"db_session_factory": mock_db_session_factory}}

    delta = await knowledge_retriever_node(state, config)

    mock_get_embedding.assert_called_once()
    mock_search_chunks.assert_called_once()

    assert "retrieved_knowledge_for_next_action" in delta
    assert (
        "Nenhuma informação específica encontrada"
        in delta["retrieved_knowledge_for_next_action"]
    )
    assert delta.get("last_processing_error") is None


@pytest.mark.asyncio
async def test_retriever_no_query_text(
    base_state_for_retriever, mock_db_session_factory
):
    """Test the case where the action parameters don't provide a query."""
    state = base_state_for_retriever
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {}  # Sem 'question_to_answer_text'

    config = {"configurable": {"db_session_factory": mock_db_session_factory}}

    delta = await knowledge_retriever_node(state, config)

    assert delta.get("retrieved_knowledge_for_next_action") is None
    assert delta.get("last_processing_error") is None  # Não é um erro, apenas skip


@pytest.mark.asyncio
async def test_retriever_embedding_fails(
    base_state_for_retriever, mock_db_session_factory
):
    """Test the case where embedding generation fails."""
    state = base_state_for_retriever
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": "Pergunta válida"}

    # Mock get_embedding para retornar None
    with patch(
        "app.services.new_agent.components.knowledge_retriever.get_embedding",
        AsyncMock(return_value=None),
    ):
        config = {"configurable": {"db_session_factory": mock_db_session_factory}}
        delta = await knowledge_retriever_node(state, config)

    # Deve retornar um contexto indicando erro, mas não necessariamente um erro no estado do grafo
    assert "Ocorreu um erro ao tentar buscar informações adicionais." in delta.get(
        "retrieved_knowledge_for_next_action", ""
    )
    # Ou poderíamos decidir retornar um erro no estado:
    # assert "RAG failed: Failed to generate query embedding." in delta.get("last_processing_error", "")
    assert (
        delta.get("last_processing_error") is None
    )  # Comportamento atual é não setar erro no estado


@pytest.mark.asyncio
@patch(
    "app.services.new_agent.components.knowledge_retriever.get_embedding",
    new_callable=AsyncMock,
)
async def test_retriever_search_fails(
    mock_get_embedding, base_state_for_retriever, mock_db_session_factory
):
    """Test the case where the search_similar_chunks function raises an exception."""
    state = base_state_for_retriever
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": "Pergunta válida"}

    mock_get_embedding.return_value = [0.5] * 10
    # Mock search_similar_chunks para levantar uma exceção
    with patch(
        "app.services.new_agent.components.knowledge_retriever.search_similar_chunks",
        AsyncMock(side_effect=Exception("DB Error")),
    ):
        config = {"configurable": {"db_session_factory": mock_db_session_factory}}
        delta = await knowledge_retriever_node(state, config)

    mock_get_embedding.assert_called_once()
    # A chamada a search_similar_chunks foi feita, mas levantou exceção

    assert "Ocorreu um erro ao tentar buscar informações adicionais." in delta.get(
        "retrieved_knowledge_for_next_action", ""
    )
    assert delta.get("last_processing_error") is None  # Comportamento atual


@pytest.mark.asyncio
async def test_retriever_missing_dependency_db(base_state_for_retriever):
    """Test failure when db_session_factory is missing."""
    state = base_state_for_retriever
    state["next_agent_action_command"] = "ANSWER_DIRECT_QUESTION"
    state["action_parameters"] = {"question_to_answer_text": "Pergunta válida"}

    config = {"configurable": {}}  # Sem db_session_factory

    delta = await knowledge_retriever_node(state, config)

    assert delta.get("retrieved_knowledge_for_next_action") is None
    assert "Missing or invalid db_session_factory" in delta.get(
        "last_processing_error", ""
    )


# Adicionar testes para outras dependências faltando (embedding, repo) se necessário
