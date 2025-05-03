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
    from .nodes_closing import initiate_close_node  # Importa o nó inicial por enquanto

    # from .nodes_closing import create_closing_subgraph # Importaremos quando estiver pronto
    CLOSING_NODES_AVAILABLE = True
    logger.info("Successfully imported Closing nodes.")
except ImportError as e:
    logger.error(f"Failed to import Closing nodes: {e}")
    CLOSING_NODES_AVAILABLE = False

    # Dummy node
    async def initiate_close_node(state, config):
        return {}


def create_closing_subgraph(checkpointer: BaseCheckpointSaver) -> StateGraph:
    """
    Builds the StateGraph for the closing process.
    (Currently only contains the initial node).
    """
    if not STATE_AVAILABLE or not CLOSING_NODES_AVAILABLE:
        raise RuntimeError("Cannot create Closing subgraph: State or nodes missing.")

    closing_workflow = StateGraph(ConversationState)
    logger.debug("Adding nodes to the Closing subgraph...")

    closing_workflow.add_node("initiate_close", initiate_close_node)

    # --- Define Closing Flow (Inicial) ---
    closing_workflow.set_entry_point("initiate_close")

    # POR FAZER: Adicionar nós (handle_final_objections, confirm_details, process_order)
    # POR FAZER: Adicionar arestas condicionais baseadas na resposta do cliente

    # Por enquanto, termina após a tentativa inicial
    closing_workflow.add_edge("initiate_close", END)

    logger.info("Compiling the Closing subgraph (INCOMPLETE)...")
    compiled_closing_graph = closing_workflow.compile(checkpointer=checkpointer)
    logger.info("Closing subgraph compiled (INCOMPLETE).")
    return compiled_closing_graph


def create_objection_subgraph(checkpointer: Checkpointer) -> StateGraph:
    """
    Builds the StateGraph for handling customer objections. It first checks
    the resolution status of a previous rebuttal (if any) and then either
    exits or proceeds to handle the current/new objection.
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

    # --- Define Objection Handling Flow ---
    objection_workflow.set_entry_point("check_resolution")  # Sempre checa primeiro

    # Roteamento APÓS a checagem de resolução
    def route_after_objection_check_inside(
        state: ConversationState,
    ) -> Literal[
        "acknowledge_and_clarify",  # Tratar objeção (persistente ou nova)
        "__end__",  # Sair do subgraph (resolvida, limite, erro)
    ]:
        resolution_status = state.get("objection_resolution_status")
        # Limpa o status para a próxima vez que o check rodar
        state["objection_resolution_status"] = None
        logger.debug(
            f"[Objection Subgraph Router] Resolution Status: {resolution_status}"
        )

        if resolution_status == "PERSISTS" or resolution_status == "NEW_OBJECTION":
            # Se a objeção persiste OU uma nova foi detectada pelo check_resolution,
            # vamos (re)iniciar o ciclo de tratamento a partir do acknowledge.
            # O acknowledge vai pegar a 'current_objection' atualizada (se for nova) ou a antiga.
            logger.debug(
                f"[Objection Subgraph Router] Status is '{resolution_status}'. Routing to acknowledge."
            )
            return "acknowledge_and_clarify"
        else:
            # Se RESOLVED, LOOP_LIMIT_EXIT, PERSISTS_ERROR ou None/Outro, termina o subgraph.
            logger.debug(
                f"[Objection Subgraph Router] Status is '{resolution_status}'. Exiting subgraph."
            )
            return END

    # Aresta Condicional após a checagem
    objection_workflow.add_conditional_edges(
        "check_resolution",
        route_after_objection_check_inside,  # Usa a função de roteamento interna
        {
            "acknowledge_and_clarify": "acknowledge_and_clarify",  # Vai para o início do tratamento
            END: END,  # Sai do subgraph
        },
    )

    # Fluxo linear de tratamento
    objection_workflow.add_edge("acknowledge_and_clarify", "retrieve_for_objection")
    objection_workflow.add_edge("retrieve_for_objection", "generate_rebuttal")
    # Termina após gerar o rebuttal (espera resposta do cliente)
    objection_workflow.add_edge("generate_rebuttal", END)

    logger.info("Compiling the Objection Handling subgraph (v3)...")
    compiled_objection_graph = objection_workflow.compile(checkpointer=checkpointer)
    logger.info("Objection Handling subgraph compiled (v3).")
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


# --- Conditional Routing Function for Main Graph ---
def route_after_classification(
    state: ConversationState,
) -> Literal[
    "invoke_spin_subgraph",  # Para investigação ativa
    "invoke_straight_line_subgraph",  # Para construir/verificar certeza antes de apresentar
    "invoke_objection_subgraph",  # Para lidar com objeções detectadas
    "invoke_closing_subgraph",  # <-- Adiciona como destino possível
    "present_capability",  # Para apresentar diretamente (menos comum agora)
    "retrieve_knowledge",  # Para responder perguntas diretas com RAG (fallback)
    "generate_rapport",  # Para saudações/abertura
    "__end__",  # Para erros na classificação
]:
    """
    Determines the next node after initial classification based on intent and stage.
    Prioritizes specific flows (Objection, SPIN, SL) over generic RAG for relevant stages.
    """
    # Pega o estado ATUALIZADO pelo nó classificador NESTA execução
    intent = state.get("intent")
    stage = state.get("current_sales_stage")  # O que o classificador ACABOU de definir
    error = state.get("error")
    # input_msg = state.get("input_message", "").lower() # Usado para checar perguntas diretas
    log_prefix = "[Router: After Classification]"
    logger.debug(
        f"{log_prefix} Intent='{intent}', Classified Stage='{stage}', Error='{error}'"
    )

    # 1. Tratamento de Erro da Classificação
    if error and "Classification failed" in error:
        logger.error(
            f"{log_prefix} Classification failed. Ending graph execution: {error}"
        )
        return END

    # 2. Saudação -> Rapport
    if intent == "Greeting":
        logger.debug(f"{log_prefix} Intent is Greeting. Routing to: generate_rapport")
        return "generate_rapport"

    # 3. Objeção Detectada -> Tratar Objeção
    # Se o classificador definiu o estágio como ObjectionHandling, essa é a prioridade.
    if stage == SALES_STAGE_OBJECTION_HANDLING:
        logger.debug(
            f"{log_prefix} Classified stage is ObjectionHandling. Routing to: invoke_objection_subgraph"
        )
        return "invoke_objection_subgraph"

    # 4. Pergunta Direta -> Tentar RAG (Prioridade sobre SPIN em estágios iniciais)
    # Verifica se é uma pergunta e se estamos em um estágio onde responder diretamente faz sentido
    is_direct_question = intent == "Question"
    # Permitir RAG em Opening e Investigation. Em Presentation, talvez seja melhor ir para SL/Objection?
    # Vamos permitir RAG em Investigation por enquanto.
    if is_direct_question and stage in [
        SALES_STAGE_OPENING,
        SALES_STAGE_INVESTIGATION,
        SALES_STAGE_UNKNOWN,
        None,
    ]:
        logger.debug(
            f"{log_prefix} Intent is Question in early/investigation stage. Routing to: retrieve_knowledge (RAG)"
        )
        # Garante que o estágio seja Investigation ao responder perguntas
        state["current_sales_stage"] = SALES_STAGE_INVESTIGATION
        return "retrieve_knowledge"

    # 5. Estágio de Investigação (e NÃO foi pergunta direta) -> Continuar SPIN
    if stage == SALES_STAGE_INVESTIGATION:
        logger.debug(
            f"{log_prefix} Stage is Investigation (not direct question). Routing to: invoke_spin_subgraph"
        )
        return "invoke_spin_subgraph"

    # 6. Estágio de Apresentação -> Verificar/Construir Certeza (Straight Line)
    if stage == SALES_STAGE_PRESENTATION:
        # Entra aqui se o SPIN identificou necessidade explícita na rodada anterior
        # OU se o classificador pulou direto para cá (menos provável com prompts ajustados)
        logger.debug(
            f"{log_prefix} Stage is Presentation. Routing to check/build certainty: invoke_straight_line_subgraph"
        )
        return "invoke_straight_line_subgraph"

    # 7. Estágio de Fechamento (Futuro)
    # if stage == SALES_STAGE_CLOSING:
    #     logger.debug(f"{log_prefix} Stage is Closing. Routing to: invoke_closing_subgraph")
    #     return "invoke_closing_subgraph"

    # 8. Rota Direta para Apresentação (Caso Especial)
    # Se, por algum motivo, o classificador decidir ir direto para apresentação
    # sem passar por SL (talvez intenção muito forte?), podemos ter essa rota.
    # No entanto, com a lógica atual, Presentation sempre vai para SL primeiro.
    # Mantendo por segurança, mas pode ser removido se a lógica for estrita.
    if (
        stage == SALES_STAGE_PRESENTATION and intent != "Objection"
    ):  # Exemplo de condição mais específica
        # Esta condição provavelmente nunca será atingida com a lógica atual
        logger.debug(
            f"{log_prefix} Classified stage is Presentation, intent is not Objection. Routing directly to: present_capability (Unlikely path)"
        )
        return "present_capability"  # Comentado pois SL é o caminho preferido

    # 9. Fallback Final -> RAG
    # Se nenhuma das condições específicas acima for atendida
    logger.debug(
        f"{log_prefix} No specific route matched for Stage '{stage}' and Intent '{intent}'. Routing to fallback: retrieve_knowledge"
    )
    # Define um estágio padrão se ainda não tiver um
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
        # logger.debug(f"{log_prefix} Certainty OK. Routing to Present Capability.")
        # return "present_capability"

        logger.debug(f"{log_prefix} Certainty OK. Routing to: invoke_closing_subgraph")
        return "invoke_closing_subgraph"
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
            "invoke_objection_subgraph": "invoke_objection_subgraph",
            "invoke_closing_subgraph": "invoke_closing_subgraph",  # <-- Adiciona rota
            "present_capability": "present_capability",
            "retrieve_knowledge": "retrieve_knowledge",
            END: END,
        },
    )
    logger.debug("Added conditional edges after 'classify_intent_and_stage'.")

    workflow.add_edge("invoke_objection_subgraph", "classify_intent_and_stage")
    logger.debug(
        "Added edge from 'invoke_objection_subgraph' back to 'classify_intent_and_stage'."
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
            "present_capability": "present_capability",  # Vai apresentar se certeza OK
            END: END,  # Termina o turno se fez declaração ou erro
        },
    )

    workflow.add_edge("invoke_closing_subgraph", "classify_intent_and_stage")
    logger.debug(
        "Added edge from 'invoke_closing_subgraph' back to 'classify_intent_and_stage'."
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
