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
        SALES_STAGE_OBJECTION_HANDLING,
        SALES_STAGE_OPENING,
        SALES_STAGE_CLOSING,
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
    SALES_STAGE_OBJECTION_HANDLING = "ObjectionHandling"
    SALES_STAGE_OPENING = "Opening"
    SALES_STAGE_UNKNOWN = "Unknown"
    SALES_STAGE_CLOSING = "Closing"

# Import Core Nodes
try:
    from .nodes_core import (
        classify_intent_and_stage_node,
        check_pending_answer_node,
        generate_rapport_node,
        retrieve_knowledge_node,
        generate_response_node,
        present_capability_node,  # Import the presentation node
        transition_after_answer_node,
        define_proposal_node,
        clarify_vague_statement_node,
        update_question_log_node,
        analyze_agent_response_node,
        handle_impasse_node,
        end_conversation_node,
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
        CERTAINTY_THRESHOLD,
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


# Import Objection Nodes
try:
    from .nodes_objection import (
        acknowledge_and_clarify_node,
        retrieve_knowledge_for_objection_node,
        generate_rebuttal_node,
        check_objection_resolved_node,
    )
    from .nodes_objection import ObjectionStatus

    OBJECTION_NODES_AVAILABLE = True
    logger.info("Successfully imported Objection subgraph creator.")
except ImportError as e:
    logger.error(f"Failed to import Objection subgraph creator: {e}")
    OBJECTION_NODES_AVAILABLE = False


try:
    from .nodes_closing import (
        initiate_close_node,
        analyze_closing_response_node,
        confirm_order_details_node,
        analyze_confirmation_response_node,
        process_order_node,
        handle_correction_node,
    )  # Importa o nó inicial por enquanto

    # from .nodes_closing import create_closing_subgraph # Importaremos quando estiver pronto
    CLOSING_NODES_AVAILABLE = True
    logger.info("Successfully imported Closing nodes.")
except ImportError as e:
    logger.error(f"Failed to import Closing nodes: {e}")
    CLOSING_NODES_AVAILABLE = False

    # Dummy node
    async def initiate_close_node(state, config):
        return {}


def create_closing_subgraph(checkpointer: Checkpointer) -> StateGraph:
    """
    Builds the StateGraph for the closing process, including confirmation,
    simplified processing, and correction handling.
    """
    if (
        not STATE_AVAILABLE
        or not CLOSING_NODES_AVAILABLE
        or not OBJECTION_NODES_AVAILABLE
    ):
        raise RuntimeError(
            "Cannot create Closing subgraph: State or nodes/subgraphs missing."
        )

    objection_subgraph_for_closing = create_objection_subgraph(checkpointer)
    logger.info("Instantiated nested Objection subgraph for Closing subgraph.")

    closing_workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes to the Closing subgraph...")

    # Nós do subgrafo de Closing
    closing_workflow.add_node("initiate_close", initiate_close_node)
    closing_workflow.add_node("analyze_response", analyze_closing_response_node)
    closing_workflow.add_node("handle_final_objection", objection_subgraph_for_closing)
    closing_workflow.add_node("confirm_details", confirm_order_details_node)
    closing_workflow.add_node(
        "analyze_confirmation", analyze_confirmation_response_node
    )
    closing_workflow.add_node("process_order", process_order_node)  # <-- Novo
    closing_workflow.add_node("handle_correction", handle_correction_node)  # <-- Novo
    closing_workflow.add_node("end_conversation_closing", end_conversation_node)

    # --- Define Closing Flow ---

    # Ponto de entrada condicional
    def route_closing_entry(
        state: ConversationState,
    ) -> Literal["initiate_close", "analyze_response", "analyze_confirmation"]:
        status = state.get("closing_status")
        log_prefix = "[Closing Entry Router]"
        if status == "ATTEMPT_MADE":
            return "analyze_response"
        elif status == "AWAITING_FINAL_CONFIRMATION":
            return "analyze_confirmation"

        elif status in [
            "ORDER_PROCESSED",
            "CONFIRMATION_REJECTED",
        ]:  # Adicionar outros estados finais se houver
            logger.debug(
                f"{log_prefix} Status '{status}' indicates previous step completed or exited. Ending subgraph immediately."
            )
            # Não reseta o status aqui, deixa o estado final registrado
            return END
        else:
            logger.debug(
                f"{log_prefix} No pending analysis (Status: {status}). Routing to initiate close."
            )
            state["closing_status"] = None
            return "initiate_close"

    closing_workflow.set_conditional_entry_point(
        route_closing_entry,
        {
            "initiate_close": "initiate_close",
            "analyze_response": "analyze_response",
            "analyze_confirmation": "analyze_confirmation",
            END: END,
        },
    )

    # Após iniciar, espera resposta
    closing_workflow.add_edge("initiate_close", END)

    # Roteamento após analisar a resposta à tentativa inicial
    def route_after_closing_analysis(
        state: ConversationState,
    ) -> Literal["handle_final_objection", "confirm_details", "__end__"]:
        status = state.get("closing_status")
        log_prefix = "[Closing Analysis Router]"
        logger.debug(f"{log_prefix} Routing based on closing status: {status}")
        if status == "PENDING_OBJECTION" or status == "PENDING_QUESTION":
            return "handle_final_objection"
        elif status == "CONFIRMED":
            return "confirm_details"
        else:
            return END

    closing_workflow.add_conditional_edges(
        "analyze_response",
        route_after_closing_analysis,
        {
            "handle_final_objection": "handle_final_objection",
            "confirm_details": "confirm_details",
            END: END,
        },
    )

    # Após tratar objeção final, termina o subgrafo
    closing_workflow.add_edge("handle_final_objection", END)

    # Após pedir confirmação de detalhes, espera resposta
    closing_workflow.add_edge("confirm_details", END)

    # Roteamento após analisar a resposta da confirmação final (ATUALIZADO)
    def route_after_final_confirmation(
        state: ConversationState,
    ) -> Literal[
        "process_order", "handle_correction", "end_conversation_closing", "__end__"
    ]:  # <-- Rotas finais
        """Routes based on the analysis of the final confirmation response."""
        status = state.get("closing_status")
        log_prefix = "[Final Confirmation Router]"
        logger.debug(
            f"{log_prefix} Routing based on final confirmation status: {status}"
        )

        if status == "FINAL_CONFIRMED":
            logger.debug(
                f"{log_prefix} Final confirmation received! Routing to process_order."
            )
            return "process_order"  # <-- Rota para processar
        elif status == "NEEDS_CORRECTION":
            logger.debug(
                f"{log_prefix} Correction needed. Routing to handle_correction."
            )
            return "handle_correction"  # <-- Rota para corrigir
        elif status == "CONFIRMATION_REJECTED":  # <-- Trata rejeição
            logger.warning(
                f"{log_prefix} Final confirmation rejected. Routing to end_conversation_closing."
            )
            state["disengagement_reason"] = (
                "Final confirmation rejected by customer."  # Opcional
            )
            return "end_conversation_closing"  # <-- Rota para finalizar
        else:  # CONFIRMATION_FAILED ou outro
            logger.warning(
                f"{log_prefix} Final confirmation failed or unknown status ({status}). Ending closing subgraph."
            )
            return END

    closing_workflow.add_conditional_edges(
        "analyze_confirmation",
        route_after_final_confirmation,
        {
            "process_order": "process_order",  # <-- Nova aresta
            "handle_correction": "handle_correction",  # <-- Nova aresta
            "end_conversation_closing": "end_conversation_closing",
            END: END,
        },
    )

    # Após processar o pedido (simplificado) ou lidar com a correção, o subgrafo termina.
    closing_workflow.add_edge("process_order", END)
    closing_workflow.add_edge(
        "handle_correction", END
    )  # O nó handle_correction agora muda o estado para sair do closing
    closing_workflow.add_edge("end_conversation_closing", END)

    logger.info(
        "Compiling the Closing subgraph (with simplified process/correction)..."
    )
    compiled_closing_graph = closing_workflow.compile(checkpointer=checkpointer)
    logger.info("Closing subgraph compiled.")
    return compiled_closing_graph


def create_objection_subgraph(checkpointer: Checkpointer) -> StateGraph:
    """
    Builds the StateGraph for handling customer objections using a conditional
    entry point based on the loop count.

    Args:
        checkpointer: The checkpointer instance for persistence.

    Returns:
        The compiled Objection Handling subgraph.
    """
    if not STATE_AVAILABLE or not OBJECTION_NODES_AVAILABLE:
        raise RuntimeError("Cannot create Objection subgraph: State or nodes missing.")

    objection_workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes to the Objection Handling subgraph...")

    # Adiciona todos os nós do ciclo de objeção
    objection_workflow.add_node("check_resolution", check_objection_resolved_node)
    objection_workflow.add_node("acknowledge_and_clarify", acknowledge_and_clarify_node)
    objection_workflow.add_node(
        "retrieve_for_objection", retrieve_knowledge_for_objection_node
    )
    objection_workflow.add_node("generate_rebuttal", generate_rebuttal_node)
    objection_workflow.add_node("end_conversation_objection", end_conversation_node)
    # --- Define Objection Handling Flow ---

    # Função para determinar o ponto de entrada
    def select_objection_entry_point(
        state: ConversationState,
    ) -> Literal["acknowledge_and_clarify", "check_resolution"]:
        """Determines entry point based on loop count."""
        loop_count = state.get("objection_loop_count", 0)
        log_prefix = "[Objection Entry Router]"
        if loop_count == 0:
            logger.debug(
                f"{log_prefix} loop_count is 0. Entering at 'acknowledge_and_clarify'."
            )
            # acknowledge_and_clarify vai extrair a objeção inicial
            return "acknowledge_and_clarify"
        else:
            logger.debug(
                f"{log_prefix} loop_count is {loop_count}. Entering at 'check_resolution'."
            )
            # check_resolution vai analisar a resposta ao rebuttal anterior
            return "check_resolution"

    # Define o ponto de entrada condicional
    objection_workflow.set_conditional_entry_point(
        select_objection_entry_point,
        {
            "acknowledge_and_clarify": "acknowledge_and_clarify",
            "check_resolution": "check_resolution",
        },
    )
    logger.debug("[Objection Subgraph] Conditional entry point set.")

    # Roteamento APÓS a checagem de resolução (quando loop_count > 0)
    def route_after_objection_check_inside(
        state: ConversationState,
    ) -> Literal[
        "acknowledge_and_clarify",  # Tratar objeção (persistente)
        "end_conversation_objection",
        "__end__",  # Sair do subgraph (resolvida, limite, erro, nova objeção - tratar no grafo principal)
    ]:
        """Routes based on the status determined by check_resolution."""
        resolution_status = state.get("objection_resolution_status")
        log_prefix = "[Objection Check Router]"
        logger.debug(f"{log_prefix} Routing based on status: {resolution_status}")
        state["objection_resolution_status"] = None  # Limpa o status

        if resolution_status == "LOOP_LIMIT_EXIT":  # <-- Trata limite de loop
            logger.warning(
                f"{log_prefix} Objection loop limit reached. Routing to end_conversation_objection."
            )
            state["disengagement_reason"] = (
                "Objection handling loop limit reached."  # Opcional
            )
            return "end_conversation_objection"  # <-- Rota para finalizar
        elif resolution_status in ["PERSISTS", "PERSISTS_ERROR"]:
            logger.debug(
                f"{log_prefix} Status '{resolution_status}' requires re-handling. Routing to acknowledge."
            )
            return "acknowledge_and_clarify"
        else:  # RESOLVED, NEW_OBJECTION (tratada no grafo principal), ou outro
            logger.debug(
                f"{log_prefix} Status is '{resolution_status}'. Exiting objection subgraph."
            )
            return END

    # Aresta Condicional APENAS após a checagem (quando loop > 0)
    objection_workflow.add_conditional_edges(
        "check_resolution",  # Nó de origem é check_resolution
        route_after_objection_check_inside,
        {
            "acknowledge_and_clarify": "acknowledge_and_clarify",  # Volta para acknowledge se persiste
            "end_conversation_objection": "end_conversation_objection",
            END: END,  # Sai se resolvida, limite, nova, etc.
        },
    )
    logger.debug("Added conditional edges after 'check_resolution'.")

    # Fluxo linear de tratamento após acknowledge (seja vindo da entrada ou do check)
    objection_workflow.add_edge("acknowledge_and_clarify", "retrieve_for_objection")
    logger.debug(
        "Added edge from 'acknowledge_and_clarify' to 'retrieve_for_objection'."
    )

    objection_workflow.add_edge("retrieve_for_objection", "generate_rebuttal")
    logger.debug("Added edge from 'retrieve_for_objection' to 'generate_rebuttal'.")

    # Termina após gerar o rebuttal (espera resposta do cliente para a próxima rodada)
    objection_workflow.add_edge("generate_rebuttal", END)
    logger.debug("Added edge from 'generate_rebuttal' to END.")

    objection_workflow.add_edge("end_conversation_objection", END)

    logger.info("Compiling the Objection Handling subgraph (with conditional entry)...")
    compiled_objection_graph = objection_workflow.compile(checkpointer=checkpointer)
    logger.info("Objection Handling subgraph compiled.")
    return compiled_objection_graph


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


def route_after_classification(
    state: ConversationState,
) -> Literal[
    "invoke_spin_subgraph",
    "invoke_straight_line_subgraph",
    "invoke_objection_subgraph",
    "invoke_closing_subgraph",
    "define_proposal",  # <-- Adiciona como destino possível
    "present_capability",
    "retrieve_knowledge",
    "generate_rapport",
    "end_conversation",
    "handle_impasse",
    "__end__",
]:
    """
    Determines the next node after initial classification, ensuring proposal
    details exist before attempting to close.
    """
    intent = state.get("intent")
    stage = state.get("current_sales_stage")
    error = state.get("error")
    # Verifica se a proposta já foi definida
    proposal_defined = bool(state.get("proposed_solution_details"))
    customer_log = state.get("customer_question_log", [])
    log_prefix = "[Router: After Classification]"
    logger.debug(
        f"{log_prefix} Intent='{intent}', Classified Stage='{stage}', Proposal Defined='{proposal_defined}', Error='{error}'"
    )

    # 1. Tratamento de Erro da Classificação
    if error and "Classification failed" in error:
        logger.error(f"{log_prefix} Classification failed. Ending: {error}")
        return END

    if intent == "Goodbye":
        logger.debug(
            f"{log_prefix} Goodbye intent detected. Routing to end_conversation."
        )
        state["disengagement_reason"] = "Customer expressed desire to end."  # Opcional
        return "end_conversation"

    if customer_log and customer_log[-1].get("status") == "repeated_ignored":
        logger.warning(f"{log_prefix} Impasse detected. Routing to handle_impasse.")
        return "handle_impasse"

    # 2. Saudação -> Rapport
    if intent == "Greeting":
        logger.debug(f"{log_prefix} Routing to: generate_rapport")
        return "generate_rapport"

    # 3. Objeção Detectada -> Tratar Objeção
    if stage == SALES_STAGE_OBJECTION_HANDLING:
        logger.debug(f"{log_prefix} Routing to: invoke_objection_subgraph")
        return "invoke_objection_subgraph"

    if intent == "VagueStatement":
        logger.debug(
            f"{log_prefix} Vague statement detected. Routing to clarify_vague_statement."
        )
        return "clarify_vague_statement"

    # 4. Tentativa de Fechamento (Intenção ou Estágio) -> Verificar Proposta
    if intent == "ClosingAttempt" or stage == SALES_STAGE_CLOSING:
        if proposal_defined:
            logger.debug(
                f"{log_prefix} Closing intent/stage detected AND proposal exists. Routing to: invoke_closing_subgraph"
            )
            # Garante que o estágio seja Closing ao entrar no subgrafo
            state["current_sales_stage"] = SALES_STAGE_CLOSING
            return "invoke_closing_subgraph"
        else:
            # Se a intenção é fechar, mas não há proposta, define a proposta primeiro!
            logger.warning(
                f"{log_prefix} Closing intent/stage detected BUT proposal MISSING. Routing to define_proposal first."
            )
            # Mantém o estágio como Presentation ou Investigation para contexto da definição da proposta?
            # Ou define como Closing e o define_proposal lida com isso?
            # Vamos manter o estágio anterior ou ir para Presentation para dar contexto.
            if (
                state.get("current_sales_stage") != SALES_STAGE_CLOSING
            ):  # Evita sobrescrever se já era Closing
                state["current_sales_stage"] = (
                    state.get("current_sales_stage") or SALES_STAGE_PRESENTATION
                )  # Garante um estágio pré-closing
            return "define_proposal"  # Define a proposta antes de fechar

    # 5. Pergunta Direta -> Tentar RAG (Prioridade sobre SPIN em estágios iniciais)
    is_direct_question = intent == "Question"
    if is_direct_question and stage in [
        SALES_STAGE_OPENING,
        SALES_STAGE_INVESTIGATION,
        SALES_STAGE_UNKNOWN,
        None,
    ]:
        logger.debug(f"{log_prefix} Routing to: retrieve_knowledge (RAG)")
        state["current_sales_stage"] = SALES_STAGE_INVESTIGATION
        return "retrieve_knowledge"

    # 6. Estágio de Investigação (e NÃO foi pergunta direta/fechamento/objeção) -> Continuar SPIN
    if stage == SALES_STAGE_INVESTIGATION:
        logger.debug(f"{log_prefix} Routing to: invoke_spin_subgraph")
        return "invoke_spin_subgraph"

    # 7. Estágio de Apresentação -> Verificar/Construir Certeza (Straight Line)
    if stage == SALES_STAGE_PRESENTATION:
        logger.debug(f"{log_prefix} Routing to: invoke_straight_line_subgraph")
        return "invoke_straight_line_subgraph"

    # 8. Rota Direta para Apresentação (Caso Especial - Menos Provável)
    # Removido pois Presentation agora vai para Straight Line

    # 9. Fallback Final -> RAG
    logger.debug(
        f"{log_prefix} No specific route matched. Fallback routing to: retrieve_knowledge"
    )
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
) -> Literal["define_proposal", "present_capability", "__end__"]:  # Destinos possíveis
    """
    Routes after the Straight Line subgraph, checking the status set by it.
    Cleans up the status AFTER routing decision.
    """
    log_prefix = "[Router: After Straight Line]"

    certainty_status = state.get("certainty_status")
    sl_error = state.get("error")
    certainty_level = state.get("certainty_level", {})

    certainty_ok = (
        all(v >= CERTAINTY_THRESHOLD for v in certainty_level.values())
        if certainty_level
        else False
    )

    logger.debug(
        f"{log_prefix} Received Status='{certainty_status}', Error='{sl_error}', Certainty Levels OK='{certainty_ok}'"
    )

    next_node: Literal["define_proposal", "present_capability", "__end__"] = END

    if sl_error and "Certainty" in sl_error:
        logger.error(
            f"{log_prefix} Error during Straight Line: {sl_error}. Ending turn."
        )
        next_node = END
    elif certainty_status == CERTAINTY_STATUS_OK or certainty_ok:
        logger.debug(f"{log_prefix} Certainty OK. Routing to: define_proposal")
        next_node = "define_proposal"
    elif certainty_status == CERTAINTY_STATUS_STATEMENT_MADE:
        logger.debug(f"{log_prefix} Certainty statement made. Ending turn.")
        next_node = END
    else:
        logger.warning(
            f"{log_prefix} Unknown or non-OK state after SL (Status: {certainty_status}). Ending turn."
        )
        next_node = END

    state["certainty_status"] = None
    logger.debug(f"{log_prefix} Certainty status cleared for next cycle.")
    # --- Fim Limpeza ---

    return next_node


def route_after_log_update(
    state: ConversationState,
) -> Literal["handle_impasse", "route_normally"]:
    """Checks the status of the last logged question to detect impasse."""
    log_prefix = "[Router: After Log Update]"
    customer_log = state.get("customer_question_log", [])
    if customer_log:
        last_entry_status = customer_log[-1].get("status")
        if last_entry_status == "repeated_ignored":
            logger.warning(
                f"{log_prefix} Last question marked as 'repeated_ignored'. Routing to handle_impasse."
            )
            return "handle_impasse"

    logger.debug(
        f"{log_prefix} No impasse detected. Proceeding to normal classification routing."
    )
    return "route_normally"  # Sinaliza para usar o roteador normal


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
            OBJECTION_NODES_AVAILABLE,
            CLOSING_NODES_AVAILABLE,
        ]
    ):
        missing = [
            name
            for name, available in [
                ("State", STATE_AVAILABLE),
                ("Core Nodes", CORE_NODES_AVAILABLE),
                ("SPIN Nodes", SPIN_NODES_AVAILABLE),
                ("Straight Line Nodes", STRAIGHT_LINE_NODES_AVAILABLE),
                ("Objection Nodes", OBJECTION_NODES_AVAILABLE),
                ("Closing Nodes", CLOSING_NODES_AVAILABLE),  # <-- Adiciona validação
            ]
            if not available
        ]
        raise RuntimeError(
            f"Cannot create main reply graph: Missing components: {', '.join(missing)}"
        )

    # --- Instantiate Subgraphs ---
    spin_subgraph = create_spin_subgraph(checkpointer=checkpointer)
    straight_line_subgraph = create_straight_line_subgraph(checkpointer=checkpointer)
    objection_subgraph = create_objection_subgraph(checkpointer=checkpointer)
    closing_subgraph = create_closing_subgraph(
        checkpointer=checkpointer
    )  # <-- Instancia subgrafo de closing

    logger.info("SPIN and Straight Line subgraphs instantiated.")

    # --- Define Main Workflow ---
    workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes and subgraphs to the main reply graph...")

    # Core Nodes
    workflow.add_node("classify_intent_and_stage", classify_intent_and_stage_node)
    workflow.add_node("check_pending_answer", check_pending_answer_node)
    workflow.add_node("clarify_vague_statement", clarify_vague_statement_node)
    workflow.add_node("generate_rapport", generate_rapport_node)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("present_capability", present_capability_node)
    workflow.add_node("transition_after_answer", transition_after_answer_node)
    workflow.add_node("end_conversation", end_conversation_node)
    workflow.add_node("update_question_log", update_question_log_node)
    workflow.add_node("handle_impasse", handle_impasse_node)
    workflow.add_node("analyze_agent_response", analyze_agent_response_node)

    # Subgraphs as Nodes
    workflow.add_node("invoke_spin_subgraph", spin_subgraph)
    workflow.add_node("invoke_straight_line_subgraph", straight_line_subgraph)
    workflow.add_node("invoke_objection_subgraph", objection_subgraph)
    workflow.add_node("invoke_closing_subgraph", closing_subgraph)
    workflow.add_node("define_proposal", define_proposal_node)

    # --- Define Entry Point ---
    workflow.set_entry_point("classify_intent_and_stage")
    logger.debug("Entry point set to 'classify_intent_and_stage'.")

    workflow.add_edge("classify_intent_and_stage", "check_pending_answer")
    logger.debug(
        "Added edge from 'classify_intent_and_stage' to 'check_pending_answer'."
    )
    workflow.add_edge("check_pending_answer", "update_question_log")

    # --- Define Edges ---
    logger.debug("Defining edges for the main reply graph...")

    # Static Edges
    workflow.add_edge("end_conversation", END)
    workflow.add_edge("generate_rapport", END)
    workflow.add_edge("retrieve_knowledge", "generate_response")
    workflow.add_edge("generate_response", "analyze_agent_response")
    workflow.add_edge("analyze_agent_response", "transition_after_answer")

    workflow.add_edge("transition_after_answer", END)
    workflow.add_edge(
        "present_capability", END
    )  # Para onde ir depois de apresentar? Talvez checar objeção/fechamento? Por enquanto, END.

    # Conditional Edge 1: After Classification
    workflow.add_conditional_edges(
        "update_question_log",
        route_after_classification,
        {
            "handle_impasse": "handle_impasse",
            "generate_rapport": "generate_rapport",
            "clarify_vague_statement": "clarify_vague_statement",
            "retrieve_knowledge": "retrieve_knowledge",
            "define_proposal": "define_proposal",
            "present_capability": "present_capability",
            "end_conversation": "end_conversation",
            "invoke_spin_subgraph": "invoke_spin_subgraph",
            "invoke_straight_line_subgraph": "invoke_straight_line_subgraph",
            "invoke_objection_subgraph": "invoke_objection_subgraph",
            "invoke_closing_subgraph": "invoke_closing_subgraph",  # <-- Adiciona rota
            END: END,
        },
    )
    logger.debug("Added conditional edges after 'classify_intent_and_stage'.")

    workflow.add_edge("invoke_objection_subgraph", END)
    logger.debug(
        "Added edge from 'invoke_objection_subgraph' to END to send the message"
    )

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
            "define_proposal": "define_proposal",
            "present_capability": "present_capability",
            END: END,
        },
    )

    workflow.add_edge("define_proposal", "invoke_closing_subgraph")

    workflow.add_edge("invoke_closing_subgraph", END)
    logger.debug(
        "Added edge from 'invoke_closing_subgraph' back to 'classify_intent_and_stage'."
    )

    workflow.add_edge("handle_impasse", END)
    # Edge 4: After Present Capability
    # O que fazer depois de apresentar? Por enquanto, termina. No futuro, checar objeções/fechamento.
    # workflow.add_edge("present_capability", END)
    # logger.debug("Added edge from 'present_capability' to END.")

    # --- Compile the Main Graph ---
    logger.info("Compiling the main reply graph...")
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    logger.info("Main reply graph compiled successfully.")
    return compiled_graph
