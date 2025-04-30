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
        check_straight_line_completion,
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

    def check_straight_line_completion(state):
        return "proceed_to_next_phase"


# --- Function to Create Straight Line Subgraph ---
def create_straight_line_subgraph(checkpointer: Checkpointer) -> StateGraph:
    """
    Builds the StateGraph for the Straight Line certainty building process.
    """
    if not STATE_AVAILABLE or not STRAIGHT_LINE_NODES_AVAILABLE:
        raise RuntimeError(
            "Cannot create Straight Line subgraph: State or nodes missing."
        )

    sl_workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes to the Straight Line subgraph...")

    sl_workflow.add_node("assess_certainty", assess_certainty_node)
    sl_workflow.add_node("select_focus", select_certainty_focus_node)
    sl_workflow.add_node(
        "retrieve_certainty_knowledge", retrieve_knowledge_for_certainty_node
    )
    sl_workflow.add_node("generate_statement", generate_certainty_statement_node)

    # --- Define Straight Line subgraph flow ---
    sl_workflow.set_entry_point("assess_certainty")
    sl_workflow.add_edge("assess_certainty", "select_focus")

    # Conditional Edge 1: After selecting focus
    sl_workflow.add_conditional_edges(
        "select_focus",
        # Simple lambda to check if focus is None (certainty met) or set
        lambda state: (
            END
            if state.get("certainty_focus") is None
            else "retrieve_certainty_knowledge"
        ),
        {
            "retrieve_certainty_knowledge": "retrieve_certainty_knowledge",
            END: END,  # End subgraph if no focus needed
        },
    )

    sl_workflow.add_edge("retrieve_certainty_knowledge", "generate_statement")

    # Conditional Edge 2: After generating statement (Loop or End)
    sl_workflow.add_conditional_edges(
        "generate_statement",
        check_straight_line_completion,  # Use the checking function
        {
            "continue_building_certainty": "assess_certainty",  # Loop back to assess again
            "proceed_to_next_phase": END,  # End subgraph if certainty met or loop limit reached
        },
    )

    logger.info("Compiling the Straight Line subgraph with checkpointer...")
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
    "retrieve_knowledge",
    "generate_rapport",
    "__end__",
]:
    intent = state.get("intent")
    stage = state.get("current_sales_stage")
    error = state.get("error")
    log_prefix = "[Router: After Classification]"
    logger.debug(f"{log_prefix} Intent='{intent}', Stage='{stage}', Error='{error}'")

    if error and "Classification failed" in error:
        return END

    if intent == "Greeting":
        logger.debug(f"{log_prefix} Routing to: generate_rapport")
        return "generate_rapport"
    elif stage == SALES_STAGE_INVESTIGATION:
        logger.debug(f"{log_prefix} Routing to: invoke_spin_subgraph")
        return "invoke_spin_subgraph"
    elif stage == SALES_STAGE_PRESENTATION:
        # Após SPIN identificar necessidade, classificador pode colocar aqui.
        # Antes de apresentar, vamos checar/construir certeza.
        logger.debug(
            f"{log_prefix} Stage is Presentation, routing to: invoke_straight_line_subgraph"
        )
        return "invoke_straight_line_subgraph"
    # Adicionar outras condições (Objection, Closing) depois
    else:
        logger.debug(f"{log_prefix} Routing to fallback: retrieve_knowledge")
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
            f"{log_prefix} Explicit need identified. Routing to: present_capability"
        )
        return "present_capability"
    else:
        # If no explicit need identified, it means a SPIN question was asked (or fallback occurred).
        # The graph turn ends here, waiting for the user's response.
        logger.debug(
            f"{log_prefix} SPIN question asked or fallback occurred. Ending current turn."
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
    workflow.add_edge("generate_response", END)
    # workflow.add_edge("present_capability", END) # Para onde ir depois de apresentar? Talvez checar objeção/fechamento? Por enquanto, END.

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
            "present_capability": "invoke_straight_line_subgraph",
            END: END,  # Se fez pergunta, termina o turno
        },
    )
    logger.debug("Added conditional edges after 'invoke_spin_subgraph'.")

    # Edge 3: After Straight Line Subgraph
    # Depois de construir certeza, apresentamos a capacidade
    workflow.add_edge("invoke_straight_line_subgraph", "present_capability")
    logger.debug(
        "Added edge from 'invoke_straight_line_subgraph' to 'present_capability'."
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
