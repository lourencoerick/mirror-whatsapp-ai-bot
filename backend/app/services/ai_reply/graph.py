# backend/app/services/ai_reply/graph.py

from langgraph.graph import StateGraph, END
from loguru import logger
from typing import Literal, Optional
from langgraph.types import Checkpointer

# Import State definition and constants
try:
    from .graph_state import (
        ConversationState,
        SALES_STAGE_INVESTIGATION,
        SALES_STAGE_PRESENTATION,
        SALES_STAGE_OPENING,
        SALES_STAGE_UNKNOWN,
        CERTAINTY_STATUS_OK,
        CERTAINTY_STATUS_STATEMENT_MADE,
    )

    STATE_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import ConversationState or Sales Stages: {e}")
    STATE_AVAILABLE = False
    from typing import TypedDict

    class ConversationState(TypedDict):
        pass

    SALES_STAGE_INVESTIGATION = "Investigation"
    SALES_STAGE_PRESENTATION = "Presentation"
    SALES_STAGE_OPENING = "Opening"
    SALES_STAGE_UNKNOWN = "Unknown"

# Import Core Nodes
try:
    from .nodes_core import (
        classify_intent_and_stage_node,
        generate_rapport_node,
        retrieve_knowledge_node,
        generate_response_node,
        present_capability_node,  # Import the presentation node
        transition_after_answer_node,
    )

    CORE_NODES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import core nodes: {e}")
    CORE_NODES_AVAILABLE = False

    # Define dummy nodes if needed
    async def classify_intent_and_stage_node(state, config):
        return {}

    async def generate_rapport_node(state, config):
        return {}

    async def retrieve_knowledge_node(state, config):
        return {}

    async def generate_response_node(state, config):
        return {}

    async def present_capability_node(state, config):
        return {}  # Dummy


# Import SPIN Nodes
try:
    from .nodes_spin import (
        analyze_history_for_spin_node,
        select_spin_question_type_node,
        generate_spin_question_node,
    )

    SPIN_NODES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import SPIN nodes: {e}")
    SPIN_NODES_AVAILABLE = False

    # Define dummy nodes if needed
    async def analyze_history_for_spin_node(state, config):
        return {}

    async def select_spin_question_type_node(state, config):
        return {}

    async def generate_spin_question_node(state, config):
        return {}


try:
    from .nodes_straight_line import (
        assess_certainty_node,
        select_certainty_focus_node,
        retrieve_knowledge_for_certainty_node,
        generate_certainty_statement_node,
    )

    STRAIGHT_LINE_NODES_AVAILABLE = True
    logger.info("Successfully imported Straight Line nodes.")
except ImportError as e:
    logger.error(f"Failed to import Straight Line nodes: {e}")
    STRAIGHT_LINE_NODES_AVAILABLE = False

    # Define dummies if needed
    async def assess_certainty_node(state, config):
        return {}

    async def select_certainty_focus_node(state, config):
        return {}

    async def retrieve_knowledge_for_certainty_node(state, config):
        return {}

    async def generate_certainty_statement_node(state, config):
        return {}


# --- Function to Create Straight Line Subgraph ---
def create_straight_line_subgraph(checkpointer: Checkpointer) -> StateGraph:
    """
    Builds the StateGraph for a SINGLE PASS of the Straight Line certainty
    building process. It assesses certainty, selects a focus (if needed),
    retrieves knowledge, generates a statement, and then ENDS, indicating
    its outcome via 'certainty_status' in the state.

    Args:
        checkpointer: The checkpointer instance for persistence.

    Returns:
        The compiled Straight Line subgraph.
    """
    if not STATE_AVAILABLE or not STRAIGHT_LINE_NODES_AVAILABLE:
        raise RuntimeError(
            "Cannot create Straight Line subgraph: State or nodes missing."
        )

    sl_workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes to the Straight Line subgraph...")

    # Nós do subgraph (como antes)
    sl_workflow.add_node("assess_certainty", assess_certainty_node)
    sl_workflow.add_node("select_focus", select_certainty_focus_node)
    sl_workflow.add_node(
        "retrieve_certainty_knowledge", retrieve_knowledge_for_certainty_node
    )
    sl_workflow.add_node("generate_statement", generate_certainty_statement_node)

    # --- Define NOVO Fluxo Linear (sem loop interno) ---
    sl_workflow.set_entry_point("assess_certainty")
    sl_workflow.add_edge("assess_certainty", "select_focus")

    # Função lambda para rotear após select_focus OU para atualizar status se OK
    def route_or_set_status_after_focus(
        state: ConversationState,
    ) -> Literal["retrieve_certainty_knowledge", "__end__"]:
        if state.get("certainty_focus") is None:
            # Certeza OK, definir status e terminar subgraph
            state["certainty_status"] = (
                CERTAINTY_STATUS_OK  # Define o status diretamente (alternativa: nó dedicado)
            )
            logger.debug(
                "[SL Subgraph Router] Certainty OK. Setting status and ending subgraph."
            )
            return END
        else:
            # Certeza precisa de reforço, continuar fluxo
            logger.debug(
                "[SL Subgraph Router] Certainty focus selected. Proceeding to retrieve knowledge."
            )
            # Limpa o status anterior, se houver
            state["certainty_status"] = None
            return "retrieve_certainty_knowledge"

    # Conditional Edge 1: After selecting focus
    sl_workflow.add_conditional_edges(
        "select_focus",
        route_or_set_status_after_focus,  # Usa a nova função lambda/lógica
        {
            "retrieve_certainty_knowledge": "retrieve_certainty_knowledge",
            END: END,
        },
    )

    sl_workflow.add_edge("retrieve_certainty_knowledge", "generate_statement")

    # --- Nó generate_statement AGORA vai para END ---
    # Precisamos garantir que ele atualize o certainty_status
    # Vamos modificar o nó generate_statement para fazer isso

    # Aresta final: Após gerar a declaração, o subgraph termina.
    sl_workflow.add_edge("generate_statement", END)
    # --- FIM NOVO Fluxo Linear ---

    logger.info(
        "Compiling the Straight Line subgraph (no internal loop) with checkpointer..."
    )
    compiled_sl_graph = sl_workflow.compile(checkpointer=checkpointer)
    logger.info("Straight Line subgraph compiled successfully.")
    return compiled_sl_graph


# --- Function to Create SPIN Subgraph ---
def create_spin_subgraph(checkpointer: Checkpointer) -> StateGraph:
    """Builds the StateGraph specifically for the SPIN selling questioning process."""
    if not STATE_AVAILABLE or not SPIN_NODES_AVAILABLE:
        raise RuntimeError("Cannot create SPIN subgraph: State or SPIN nodes missing.")

    spin_workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes to the SPIN subgraph...")
    spin_workflow.add_node("analyze_history_for_spin", analyze_history_for_spin_node)
    spin_workflow.add_node("select_spin_question_type", select_spin_question_type_node)
    spin_workflow.add_node("generate_spin_question", generate_spin_question_node)

    # Define SPIN subgraph flow
    spin_workflow.set_entry_point("analyze_history_for_spin")
    spin_workflow.add_edge("analyze_history_for_spin", "select_spin_question_type")
    spin_workflow.add_edge("select_spin_question_type", "generate_spin_question")

    # The subgraph ends after attempting to generate the question.
    # If generate_spin_question_node returns empty (because type was None),
    # the main graph needs to know this via the state.
    spin_workflow.add_edge("generate_spin_question", END)

    logger.info("Compiling the SPIN subgraph...")
    compiled_spin_graph = spin_workflow.compile(checkpointer=checkpointer)
    logger.info("SPIN subgraph compiled successfully.")
    return compiled_spin_graph


# --- Conditional Routing Function for Main Graph ---
def route_after_classification(
    state: ConversationState,
) -> Literal[
    "invoke_spin_subgraph",
    "invoke_straight_line_subgraph",
    "present_capability",
    "retrieve_knowledge",  # Rota RAG padrão
    "generate_rapport",
    "__end__",
]:
    """
    Determines the next node after initial classification.
    Prioritizes RAG for direct questions before entering specific sales flows.
    """
    intent = state.get("intent")
    stage = state.get("current_sales_stage")
    error = state.get("error")
    input_msg = state.get(
        "input_message", ""
    ).lower()  # Pega a última mensagem para análise simples
    log_prefix = "[Router: After Classification]"
    logger.debug(f"{log_prefix} Intent='{intent}', Stage='{stage}', Error='{error}'")

    if error and "Classification failed" in error:
        logger.error(f"{log_prefix} Classification failed. Ending.")
        return END

    # 1. Respostas Simples Primeiro
    if intent == "Greeting":
        logger.debug(f"{log_prefix} Intent is Greeting. Routing to: generate_rapport")
        return "generate_rapport"

    # 2. Perguntas Diretas -> Tentar RAG Primeiro
    # Se a intenção foi classificada como Pergunta OU contém palavras interrogativas comuns
    # E NÃO estamos explicitamente em um estágio avançado como Closing/Objection (ainda não implementado)
    is_direct_question = intent == "Question"  # or any(
    # kw in input_msg for kw in ["como", "qual", "onde", "quando", "quanto", "?"]
    # )
    is_early_stage = stage in [
        None,
        SALES_STAGE_OPENING,
        SALES_STAGE_INVESTIGATION,
        SALES_STAGE_UNKNOWN,
    ]  # Adicione outros estágios onde RAG é preferível

    if is_direct_question and is_early_stage:
        logger.debug(
            f"{log_prefix} Intent is Question in early stage. Routing to: retrieve_knowledge (RAG)"
        )
        # Define o estágio como Investigation se ainda não estiver, pois estamos respondendo perguntas
        state["current_sales_stage"] = SALES_STAGE_INVESTIGATION
        return "retrieve_knowledge"  # Tenta responder com RAG

    # 3. Lógica de Estágio Específico (SPIN, Straight Line, etc.)
    # Só entra aqui se NÃO for uma saudação ou pergunta direta inicial
    if stage == SALES_STAGE_INVESTIGATION:
        # Se já estamos em Investigação e NÃO foi uma pergunta direta respondível por RAG,
        # então provavelmente queremos fazer uma pergunta SPIN.
        logger.debug(
            f"{log_prefix} Stage is Investigation (not direct question). Routing to: invoke_spin_subgraph"
        )
        return "invoke_spin_subgraph"
    elif stage == SALES_STAGE_PRESENTATION:
        logger.debug(
            f"{log_prefix} Stage is Presentation. Routing to: invoke_straight_line_subgraph"
        )
        return "invoke_straight_line_subgraph"
    # Adicionar condições para outros estágios aqui...

    # 4. Fallback Final
    # Se nenhuma das condições acima for atendida, usa RAG como último recurso.
    logger.debug(
        f"{log_prefix} No specific route matched. Routing to fallback: retrieve_knowledge"
    )
    # Garante que o estágio seja definido para algo razoável se ainda for None/Opening
    if stage in [None, SALES_STAGE_OPENING]:
        state["current_sales_stage"] = SALES_STAGE_INVESTIGATION
    return "retrieve_knowledge"


# --- Conditional Routing Function AFTER SPIN Subgraph ---
def route_after_spin(
    state: ConversationState,
) -> Literal["present_capability", "__end__"]:
    """
    Determines the next step after the SPIN subgraph has run.
    If an explicit need was identified, moves to presentation.
    Otherwise, ends the current turn (waiting for user response to SPIN question).
    """
    log_prefix = "[Router: After SPIN]"
    explicit_need_identified = state.get("explicit_need_identified", False)
    spin_error = state.get("error")  # Check for errors within SPIN subgraph

    if explicit_need_identified:
        state["explicit_need_identified"] = False

    logger.debug(
        f"{log_prefix} Explicit Need Identified='{explicit_need_identified}', Error='{spin_error}'"
    )

    if spin_error and "SPIN" in spin_error:  # Check for SPIN specific errors
        logger.error(
            f"{log_prefix} Error during SPIN subgraph execution: {spin_error}. Ending turn."
        )
        return END
    elif explicit_need_identified:
        logger.debug(
            f"{log_prefix} Explicit need identified. Routing to: invoke_straight_line_subgraph"
        )
        return "invoke_straight_line_subgraph"
    else:
        # If no explicit need identified, it means a SPIN question was asked (or fallback occurred).
        # The graph turn ends here, waiting for the user's response.
        logger.debug(
            f"{log_prefix} SPIN question asked or fallback occurred. Ending current turn."
        )
        return END


def route_after_straight_line(
    state: ConversationState,
) -> Literal["present_capability", "__end__"]:
    """Roteia após o subgraph Straight Line, baseado no seu resultado ('certainty_status')."""
    log_prefix = "[Router: After Straight Line]"
    certainty_status = state.get("certainty_status")
    sl_error = state.get("error")  # Verifica erros do SL

    logger.debug(
        f"{log_prefix} Certainty Status='{certainty_status}', Error='{sl_error}'"
    )

    # Limpa o status para a próxima execução (importante!)
    state["certainty_status"] = None

    if sl_error and "Certainty" in sl_error:
        logger.error(
            f"{log_prefix} Error during Straight Line: {sl_error}. Ending turn."
        )
        return END
    elif certainty_status == CERTAINTY_STATUS_OK:
        # Certeza atingiu o limiar ou já estava OK
        logger.debug(f"{log_prefix} Certainty OK. Routing to Present Capability.")
        return "present_capability"
    elif certainty_status == CERTAINTY_STATUS_STATEMENT_MADE:
        # Uma declaração foi feita, precisamos esperar a resposta do cliente
        logger.debug(f"{log_prefix} Certainty statement made. Ending turn.")
        return END
    else:
        # Caso inesperado (subgraph terminou sem definir status?)
        logger.warning(
            f"{log_prefix} Unknown state after Straight Line (Status: {certainty_status}). Ending turn."
        )
        return END


# --- Function to Create the Main Reply Graph (Atualizada) ---
def create_reply_graph(checkpointer: Checkpointer) -> StateGraph:
    """
    Builds the main graph, incorporating SPIN and Straight Line subgraphs.
    """
    # --- Validações ---
    if not all(
        [
            STATE_AVAILABLE,
            CORE_NODES_AVAILABLE,
            SPIN_NODES_AVAILABLE,
            STRAIGHT_LINE_NODES_AVAILABLE,
        ]
    ):
        missing = [
            name
            for name, available in [
                ("State", STATE_AVAILABLE),
                ("Core Nodes", CORE_NODES_AVAILABLE),
                ("SPIN Nodes", SPIN_NODES_AVAILABLE),
                ("Straight Line Nodes", STRAIGHT_LINE_NODES_AVAILABLE),
            ]
            if not available
        ]
        raise RuntimeError(
            f"Cannot create main reply graph: Missing components: {', '.join(missing)}"
        )

    # --- Instantiate Subgraphs ---
    spin_subgraph = create_spin_subgraph(checkpointer=checkpointer)
    straight_line_subgraph = create_straight_line_subgraph(
        checkpointer=checkpointer
    )  # <-- INSTANCIA NOVO SUBGRAPH
    logger.info("SPIN and Straight Line subgraphs instantiated.")

    # --- Define Main Workflow ---
    workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes and subgraphs to the main reply graph...")

    # Core Nodes
    workflow.add_node("classify_intent_and_stage", classify_intent_and_stage_node)
    workflow.add_node("generate_rapport", generate_rapport_node)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("present_capability", present_capability_node)
    workflow.add_node("transition_after_answer", transition_after_answer_node)

    # Subgraphs as Nodes
    workflow.add_node("invoke_spin_subgraph", spin_subgraph)
    workflow.add_node(
        "invoke_straight_line_subgraph", straight_line_subgraph
    )  # <-- ADICIONA NOVO SUBGRAPH

    # --- Define Entry Point ---
    workflow.set_entry_point("classify_intent_and_stage")
    logger.debug("Entry point set to 'classify_intent_and_stage'.")

    # --- Define Edges ---
    logger.debug("Defining edges for the main reply graph...")

    # Static Edges
    workflow.add_edge("generate_rapport", END)
    workflow.add_edge("retrieve_knowledge", "generate_response")
    workflow.add_edge("generate_response", "transition_after_answer")
    workflow.add_edge("transition_after_answer", END)
    workflow.add_edge(
        "present_capability", END
    )  # Para onde ir depois de apresentar? Talvez checar objeção/fechamento? Por enquanto, END.

    # Conditional Edge 1: After Classification
    workflow.add_conditional_edges(
        "classify_intent_and_stage",
        route_after_classification,
        {
            "generate_rapport": "generate_rapport",
            "invoke_spin_subgraph": "invoke_spin_subgraph",
            "invoke_straight_line_subgraph": "invoke_straight_line_subgraph",
            "present_capability": "present_capability",
            "retrieve_knowledge": "retrieve_knowledge",
            END: END,
        },
    )
    logger.debug("Added conditional edges after 'classify_intent_and_stage'.")

    # Conditional Edge 2: After SPIN Subgraph
    workflow.add_conditional_edges(
        "invoke_spin_subgraph",
        route_after_spin,  # Função inalterada por enquanto
        {
            # Se necessidade explícita foi identificada, vamos construir certeza antes de apresentar
            "invoke_straight_line_subgraph": "invoke_straight_line_subgraph",
            END: END,  # Se fez pergunta, termina o turno
        },
    )
    logger.debug("Added conditional edges after 'invoke_spin_subgraph'.")

    # Edge 3: After Straight Line Subgraph
    # Depois de construir certeza, apresentamos a capacidade
    workflow.add_conditional_edges(
        "invoke_straight_line_subgraph",  # Nó de origem
        route_after_straight_line,  # Nova função de roteamento
        {
            "present_capability": "present_capability",  # Vai apresentar se certeza OK
            END: END,  # Termina o turno se fez declaração ou erro
        },
    )
    # Edge 4: After Present Capability
    # O que fazer depois de apresentar? Por enquanto, termina. No futuro, checar objeções/fechamento.
    workflow.add_edge("present_capability", END)
    logger.debug("Added edge from 'present_capability' to END.")

    # --- Compile the Main Graph ---
    logger.info("Compiling the main reply graph...")
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("Main reply graph compiled successfully.")
    return compiled_graph
