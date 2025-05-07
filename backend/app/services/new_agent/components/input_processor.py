# backend/app/services/ai_reply/new_agent/components/input_processor.py

from typing import Dict, List, Optional, Any
from loguru import logger

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage  # Para _format_recent_chat_history
from langchain_core.prompts import ChatPromptTemplate

try:
    from trustcall import create_extractor

    TRUSTCALL_AVAILABLE = True
except ImportError:
    TRUSTCALL_AVAILABLE = False
    logger.warning(
        "TrustCall not available. InputProcessor will rely on llm.with_structured_output."
    )

# Importar os schemas Pydantic
from ..schemas.input_analysis import (
    InitialUserInputAnalysis,
    UserInputAnalysisOutput,
    ExtractedQuestionAnalysis,
    InitiallyExtractedQuestion,
    SingleRepetitionCheckOutput,
    SimplifiedCustomerQuestionStatusType,
)

# Importar a definição do estado principal
from ..state_definition import RichConversationState, CustomerQuestionEntry


# --- Constantes ---
SIMILARITY_THRESHOLD = (
    0.85  # Exemplo, não usado na versão LLM de repetição, mas pode ser para embeddings
)
RECENT_HISTORY_LIMIT = 5  # Número de mensagens recentes para incluir no prompt


# --- Funções Auxiliares ---
def _format_recent_chat_history(
    messages: List[BaseMessage], limit: int = RECENT_HISTORY_LIMIT
) -> str:
    """
    Formats the recent chat history for the LLM prompt from LangChain BaseMessage objects.
    Excludes the very last message if it's the current user input.
    """
    if not messages:
        return "Nenhum histórico de conversa recente."

    # Consider messages up to the one before last, as the last one is current_user_input_text
    history_to_format = messages[-(limit + 1) : -1] if len(messages) > 1 else []
    if not history_to_format and len(messages) == 1:  # Only current user message exists
        return "Esta é a primeira mensagem da conversa."

    formatted_lines = []
    for msg in history_to_format:
        role = "Agente"
        if msg.type == "human":
            role = "Usuário"
        elif msg.type == "system":  # Should not happen in recent history normally
            role = "Sistema"

        content = getattr(msg, "content", "")
        formatted_lines.append(f"{role}: {content}")

    return (
        "\n".join(formatted_lines)
        if formatted_lines
        else "Nenhum histórico de conversa anterior relevante."
    )


async def _call_structured_llm(
    llm: BaseChatModel,
    prompt_template_str: str,
    prompt_values: Dict[str, Any],
    output_schema: Any,  # Pydantic Model (e.g., InitialUserInputAnalysis)
    node_name_for_logging: str,
) -> Optional[Any]:
    """Helper function to call LLM for structured output using TrustCall or with_structured_output."""
    try:
        if TRUSTCALL_AVAILABLE:
            # TrustCall's create_extractor might be better initialized once if config doesn't change
            extractor = create_extractor(
                llm=llm,
                tools=[output_schema],
                tool_choice=output_schema.__name__,
            )
            formatted_prompt = prompt_template_str.format(**prompt_values)
            logger.debug(
                f"[{node_name_for_logging}] Invoking TrustCall extractor with prompt:\n{formatted_prompt[:500]}..."
            )
            result = await extractor.ainvoke(formatted_prompt)
            logger.debug(
                f"[{node_name_for_logging}] Raw result from TrustCall: {result}"
            )

            responses = result.get("responses")
            if isinstance(responses, list) and len(responses) > 0:
                # Pydantic validation happens here
                return output_schema.model_validate(responses[0])
            else:
                logger.error(
                    f"[{node_name_for_logging}] TrustCall did not return expected 'responses' list or it's empty. Result: {result}"
                )
                return None
        elif hasattr(llm, "with_structured_output"):
            chat_prompt = ChatPromptTemplate.from_template(prompt_template_str)
            structured_llm_chain = chat_prompt | llm.with_structured_output(
                output_schema
            )
            logger.debug(
                f"[{node_name_for_logging}] Invoking LLM with_structured_output with values: {prompt_values}"
            )
            return await structured_llm_chain.ainvoke(prompt_values)
        else:
            logger.error(
                f"[{node_name_for_logging}] No structured output method available (TrustCall or with_structured_output)."
            )
            return None
    except Exception as e:
        logger.exception(
            f"[{node_name_for_logging}] Error during structured LLM call: {e}"
        )
        return None


# --- Sub-Etapa: Extração Inicial ---
PROMPT_INITIAL_EXTRACTION = """
Você é um Analista de Conversas de Vendas IA altamente preciso e meticuloso. Sua tarefa é analisar a "ÚLTIMA MENSAGEM DO CLIENTE" no contexto do "HISTÓRICO DA CONVERSA" e da "ÚLTIMA AÇÃO DO AGENTE" (o que o agente disse/perguntou imediatamente antes da mensagem do cliente).

**Contexto Fornecido:**

1.  **ÚLTIMA MENSAGEM DO CLIENTE:**
    ```
    {last_user_message_text}
    ```

2.  **ÚLTIMA AÇÃO DO AGENTE (Texto gerado pelo agente no turno anterior):**
    ```
    {last_agent_action_text}
    ```
    (Se for o início da conversa, este campo será "N/A - Início da conversa" ou similar.)

3.  **HISTÓRICO RECENTE DA CONVERSA (excluindo a "ÚLTIMA MENSAGEM DO CLIENTE"):**
    (Formato: "Usuário: [texto]" ou "Agente: [texto]")
    ```
    {recent_chat_history}
    ```

**Sua Tarefa de Análise (Preencha o JSON `InitialUserInputAnalysis` com precisão):**

1.  **`overall_intent`**: Classifique a intenção principal e predominante da "ÚLTIMA MENSAGEM DO CLIENTE".
    Valores possíveis: "Greeting", "Farewell", "Questioning", "StatingInformationOrOpinion", "ExpressingObjection", "ExpressingNeedOrPain", "RespondingToAgent", "VagueOrUnclear", "OffTopic", "PositiveFeedback", "NegativeFeedback", "RequestingClarificationFromAgent".

2.  **`initially_extracted_questions`** (Lista de `InitiallyExtractedQuestion`):
    *   Identifique TODAS as perguntas distintas e explícitas na "ÚLTIMA MENSAGEM DO CLIENTE".
    *   Para CADA pergunta identificada:
        *   `question_text`: O texto central e normalizado da pergunta. Remova frases introdutórias como "Eu gostaria de saber se..." e foque no núcleo da questão.

3.  **`extracted_objections`** (Lista de `ExtractedObjection`):
    *   Identifique quaisquer objeções claras (ao produto, preço, processo, tempo, valor, etc.).
    *   Para cada objeção: `objection_text`: O texto central que expressa a objeção.

4.  **`extracted_needs_or_pains`** (Lista de `ExtractedNeedOrPain`):
    *   Identifique se o cliente descreve alguma necessidade explícita ou ponto de dor/problema.
    *   Para cada um: `text` (o texto descritivo) e `type` ("need" ou "pain_point").

5.  **`analysis_of_response_to_agent_action`** (Objeto `PendingAgentActionResponseAnalysis`):
    *   Avalie como a "ÚLTIMA MENSAGEM DO CLIENTE" se relaciona com a "ÚLTIMA AÇÃO DO AGENTE".
    *   `user_response_to_agent_action`: Escolha UM dos seguintes:
        *   "answered_clearly": O cliente respondeu direta e completamente à pergunta/ação específica do agente.
        *   "partially_answered": O cliente abordou a pergunta/ação do agente, mas de forma incompleta, vaga ou evasiva.
        *   "ignored_agent_action": O cliente NÃO abordou a pergunta/ação do agente e mudou de assunto, fez uma nova pergunta não relacionada, ou levantou uma objeção não relacionada.
        *   "acknowledged_action": O cliente apenas reconheceu a declaração do agente (ex: "ok", "entendi", "certo") sem adicionar nova informação substancial ou responder a uma pergunta implícita.
        *   "not_applicable": A "ÚLTIMA AÇÃO DO AGENTE" não era uma pergunta direta ou não esperava uma resposta específica.

6.  **`is_primarily_vague_statement`**: A "ÚLTIMA MENSAGEM DO CLIENTE", em sua essência, é uma declaração vaga, expressa incerteza geral ou confusão, sem apresentar uma pergunta ou objeção específica e clara? (true/false). Defina como `false` a menos que seja claramente vago.

7.  **`is_primarily_off_topic`**: A "ÚLTIMA MENSAGEM DO CLIENTE" é predominantemente sobre um tópico não relacionado à venda, aos produtos/serviços da empresa, ou ao fluxo da conversa estabelecido? (true/false). Defina como `false` a menos que seja claramente off-topic.

**Instruções Cruciais:**
*   Seja extremamente preciso ao preencher cada campo.
*   Se um campo de lista (ex: `extracted_objections`) não tiver itens, retorne uma lista vazia `[]`.
*   NÃO realize análise de repetição de perguntas nesta etapa. Apenas extraia o texto das perguntas.

Responda APENAS com o objeto JSON formatado de acordo com o schema `InitialUserInputAnalysis` e seus sub-modelos. Não inclua nenhuma explicação ou texto adicional fora do JSON.
"""


async def initial_input_extraction_sub_step(
    last_user_message_text: str,
    last_agent_action_text: Optional[str],
    recent_chat_history_str: str,
    llm_fast: BaseChatModel,
) -> Optional[InitialUserInputAnalysis]:
    """
    Performs the initial LLM call to extract information from user input.
    """
    node_name = "initial_input_extraction_sub_step"
    logger.info(f"[{node_name}] Starting initial input extraction...")

    prompt_values = {
        "last_user_message_text": last_user_message_text,
        "last_agent_action_text": last_agent_action_text or "N/A - Início da conversa",
        "recent_chat_history": recent_chat_history_str,
    }

    analysis_object = await _call_structured_llm(
        llm=llm_fast,
        prompt_template_str=PROMPT_INITIAL_EXTRACTION,
        prompt_values=prompt_values,
        output_schema=InitialUserInputAnalysis,
        node_name_for_logging=node_name,
    )

    if analysis_object:
        logger.info(
            f"[{node_name}] Initial extraction successful. Intent: {analysis_object.overall_intent}"
        )
    else:
        logger.error(f"[{node_name}] Initial extraction failed.")
    return analysis_object


# --- Sub-Etapa: Análise de Repetição de Perguntas (usando LLM) ---
PROMPT_SINGLE_REPETITION_CHECK = """
Você é um especialista em análise semântica. Determine se a "NOVA PERGUNTA" é uma repetição semântica da "PERGUNTA REGISTRADA NO LOG".
Ignore pequenas variações de palavras ou ordem, foque no significado central e na intenção da pergunta.

NOVA PERGUNTA:
"{new_question_text}"

PERGUNTA REGISTRADA NO LOG:
"{logged_question_core_text}"

A "NOVA PERGUNTA" é uma repetição semântica da "PERGUNTA REGISTRADA NO LOG"?
Responda APENAS com um objeto JSON contendo o campo "is_semantic_repetition" (true/false),
seguindo o schema SingleRepetitionCheckOutput.
"""


async def check_single_repetition_with_llm(
    new_question_text: str,
    logged_question_core_text: str,
    llm_fast: BaseChatModel,
) -> bool:
    """
    Uses an LLM to check if a new question is a semantic repetition of a single logged question.
    """
    node_name = "check_single_repetition_with_llm"
    if not logged_question_core_text:  # Sanity check
        return False

    prompt_values = {
        "new_question_text": new_question_text,
        "logged_question_core_text": logged_question_core_text,
    }

    check_output = await _call_structured_llm(
        llm=llm_fast,
        prompt_template_str=PROMPT_SINGLE_REPETITION_CHECK,
        prompt_values=prompt_values,
        output_schema=SingleRepetitionCheckOutput,
        node_name_for_logging=node_name,
    )

    if check_output:
        return check_output.is_semantic_repetition

    logger.warning(
        f"[{node_name}] Failed to get repetition check result for: '{new_question_text[:30]}' vs '{logged_question_core_text[:30]}'. Defaulting to False."
    )
    return False  # Default to not a repetition on error


async def analyze_question_repetitions_sub_step(
    initially_extracted_questions: List[InitiallyExtractedQuestion],
    customer_question_log: List[CustomerQuestionEntry],
    llm_fast: BaseChatModel,
    current_turn_number: int,  # Needed to avoid comparing with self if log is updated mid-turn
) -> List[ExtractedQuestionAnalysis]:
    """
    Analyzes extracted questions for repetition against a log of previous questions using an LLM.
    """
    node_name = "analyze_question_repetitions_sub_step_llm"
    logger.info(
        f"[{node_name}] Starting LLM-based repetition analysis for {len(initially_extracted_questions)} questions."
    )

    final_analyzed_questions: List[ExtractedQuestionAnalysis] = []

    if not initially_extracted_questions:
        return []

    # Sort log by turn, most recent first, to find the latest relevant original question
    # This helps if a question was asked multiple times and answered differently each time.
    # We care about the most recent attempt to answer it.
    sorted_log_entries = sorted(
        customer_question_log, key=lambda x: x.get("turn_asked", 0), reverse=True
    )

    for init_q in initially_extracted_questions:
        logger.debug(
            f"[{node_name}] Analyzing for repetition: '{init_q.question_text[:50]}...'"
        )

        is_repetition_found = False
        status_original_answer: Optional[SimplifiedCustomerQuestionStatusType] = None
        original_turn: Optional[int] = None
        original_core_text: Optional[str] = None

        for log_entry in sorted_log_entries:
            # Avoid comparing a question with itself if it somehow got into the log for the current turn already
            # (should not happen with correct StateUpdater logic, but good safeguard)
            if (
                log_entry.get("turn_asked", -1) == current_turn_number
                and log_entry.get("extracted_question_core", "") == init_q.question_text
            ):
                continue

            is_single_match = await check_single_repetition_with_llm(
                new_question_text=init_q.question_text,
                logged_question_core_text=log_entry.get("extracted_question_core", ""),
                llm_fast=llm_fast,
            )

            if is_single_match:
                is_repetition_found = True
                log_status = log_entry.get(
                    "status"
                )  # This is CustomerQuestionStatusType

                # Map CustomerQuestionStatusType from state_definition to SimplifiedCustomerQuestionStatusType for the schema
                if log_status == "answered_satisfactorily":
                    status_original_answer = "answered_satisfactorily"
                elif log_status == "answered_with_fallback":
                    status_original_answer = "answered_with_fallback"
                # Add more mappings if SimplifiedCustomerQuestionStatusType expands
                else:  # e.g., "newly_asked", "pending_agent_answer", "repetition_..."
                    # For these, the "original answer" status is effectively unknown or not yet given
                    status_original_answer = "unknown_previous_status"

                original_turn = log_entry.get("turn_asked")
                original_core_text = log_entry.get("extracted_question_core")
                logger.info(
                    f"    LLM identified repetition of '{init_q.question_text[:30]}...' with log entry from turn {original_turn}: '{original_core_text[:30]}...' (Original Answer Status: {status_original_answer})"
                )
                break  # Found the most recent relevant match

        final_analyzed_questions.append(
            ExtractedQuestionAnalysis(
                question_text=init_q.question_text,
                is_repetition=is_repetition_found,
                status_of_original_answer=status_original_answer,
                original_question_turn=original_turn,
                original_question_core_text=original_core_text,
            )
        )

    logger.info(f"[{node_name}] LLM-based repetition analysis complete.")
    return final_analyzed_questions


# --- Nó Principal do LangGraph ---
async def process_user_input_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    LangGraph node to process the user's input.
    It extracts information, analyzes for repetitions, and prepares the
    analysis for the StateUpdater.
    """
    node_name = "process_user_input_node"
    logger.info(
        f"--- Starting Node: {node_name} (Turn: {state.get('current_turn_number', 0)}) ---"
    )

    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )
    if not llm_fast:
        logger.error(
            f"[{node_name}] llm_fast_instance not found in config. Cannot proceed."
        )
        return {
            "user_input_analysis_result": None,
            "last_processing_error": "LLM for input processing unavailable.",
        }

    last_user_message_text = state.get("current_user_input_text", "")
    if not last_user_message_text:
        logger.warning(
            f"[{node_name}] No current_user_input_text in state. Skipping processing."
        )
        return {"user_input_analysis_result": None}

    last_agent_action = state.get("last_agent_action")
    last_agent_action_text = None
    if last_agent_action and isinstance(last_agent_action, dict):
        last_agent_action_text = last_agent_action.get("action_generation_text")

    # messages are List[BaseMessage]
    raw_messages_history: List[BaseMessage] = state.get("messages", [])
    recent_chat_history_str = _format_recent_chat_history(
        raw_messages_history, limit=RECENT_HISTORY_LIMIT
    )

    # 1. Extração Inicial
    initial_analysis = await initial_input_extraction_sub_step(
        last_user_message_text=last_user_message_text,
        last_agent_action_text=last_agent_action_text,
        recent_chat_history_str=recent_chat_history_str,
        llm_fast=llm_fast,
    )

    if not initial_analysis:
        logger.error(f"[{node_name}] Initial input extraction failed.")
        return {
            "user_input_analysis_result": None,
            "last_processing_error": "Initial input extraction LLM call failed.",
        }

    # 2. Análise de Repetição
    updated_questions_with_repetition_info = await analyze_question_repetitions_sub_step(
        initially_extracted_questions=initial_analysis.initially_extracted_questions,
        customer_question_log=state.get("customer_question_log", []),
        llm_fast=llm_fast,
        current_turn_number=state.get("current_turn_number", 0),
    )

    # 3. Combinar para formar o UserInputAnalysisOutput final
    final_analysis = UserInputAnalysisOutput(
        overall_intent=initial_analysis.overall_intent,
        extracted_questions=updated_questions_with_repetition_info,
        extracted_objections=initial_analysis.extracted_objections,
        extracted_needs_or_pains=initial_analysis.extracted_needs_or_pains,
        analysis_of_response_to_agent_action=initial_analysis.analysis_of_response_to_agent_action,
        is_primarily_vague_statement=initial_analysis.is_primarily_vague_statement,
        is_primarily_off_topic=initial_analysis.is_primarily_off_topic,
    )

    logger.info(
        f"[{node_name}] Final user input analysis complete. Intent: {final_analysis.overall_intent}, Questions: {len(final_analysis.extracted_questions)}"
    )
    if final_analysis.extracted_questions:
        for q_idx, q_info in enumerate(final_analysis.extracted_questions):
            logger.debug(
                f"  Q{q_idx+1}: '{q_info.question_text[:50]}...' Repetition: {q_info.is_repetition} (Original Turn: {q_info.original_question_turn}, Original Answer: {q_info.status_of_original_answer})"
            )

    # Retorna o resultado para ser adicionado ao estado pelo LangGraph
    # O StateUpdaterNode usará state.get("user_input_analysis_result")
    return {"user_input_analysis_result": final_analysis.model_dump()}
