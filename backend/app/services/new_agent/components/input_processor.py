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
    ReactionToPresentation,
    ObjectionAfterRebuttalStatus,
)

# Importar a definição do estado principal
from ..state_definition import (
    RichConversationState,
    CustomerQuestionEntry,
    PendingAgentAction,
)


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
    Formats the recent chat history for inclusion in LLM prompts.

    Excludes the latest message (assumed to be the current user input being processed).
    Formats messages with 'Usuário:' or 'Agente:' prefixes.

    Args:
        messages: The list of BaseMessage objects from the conversation state.
        limit: The maximum number of *past* messages (excluding the current one)
               to include.

    Returns:
        A formatted string representing the recent chat history, or a
        placeholder string if the history is empty or only contains the
        current message.
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
    """
    Helper function to call an LLM and attempt structured output extraction.

    Uses TrustCall's create_extractor if available, otherwise falls back to
    LangChain's llm.with_structured_output method if the LLM supports it.

    Args:
        llm: The language model instance.
        prompt_template_str: The string template for the prompt.
        prompt_values: A dictionary of values to format the prompt template.
        output_schema: The Pydantic model defining the desired output structure.
        node_name_for_logging: A string identifier for logging messages.

    Returns:
        An instance of the output_schema populated with the LLM's response,
        or None if the structured call fails or no valid output is extracted.
    """
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
                f"[{node_name_for_logging}] Invoking TrustCall extractor with prompt:\n{formatted_prompt[:50000]}..."
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
Você é um Analista de Conversas de Vendas IA altamente preciso e meticuloso. Sua tarefa é analisar a "ÚLTIMA MENSAGEM DO CLIENTE" no contexto do "HISTÓRICO DA CONVERSA", da "ÚLTIMA AÇÃO DO AGENTE" e do "TIPO DA ÚLTIMA AÇÃO DO AGENTE".

**Contexto Fornecido:**

1.  **ÚLTIMA MENSAGEM DO CLIENTE:**
    ```
    {last_user_message_text}
    ```

2.  **ÚLTIMA AÇÃO DO AGENTE (Texto gerado pelo agente no turno anterior):**
    ```
    {last_agent_action_text}
    ```

3.  **TIPO DA ÚLTIMA AÇÃO DO AGENTE:** (Ex: "PRESENT_SOLUTION_OFFER", "GENERATE_REBUTTAL", "ASK_SPIN_QUESTION", "N/A")
    ```
    {last_agent_action_type} 
    ```
    (Se "GENERATE_REBUTTAL", o texto da objeção original tratada será: "{original_objection_text_if_rebuttal}")

4.  **HISTÓRICO RECENTE DA CONVERSA (excluindo a "ÚLTIMA MENSAGEM DO CLIENTE"):**
    ```
    {recent_chat_history}
    ```

**Sua Tarefa de Análise (Preencha o JSON `InitialUserInputAnalysis` com precisão):**

1.   **`overall_intent`**: Classifique a intenção principal da "ÚLTIMA MENSAGEM DO CLIENTE".
    Valores possíveis: "Greeting", "Farewell", "Questioning", "StatingInformationOrOpinion", "ExpressingObjection", "ExpressingNeedOrPain", "RespondingToAgent", "VagueOrUnclear", "OffTopic", "PositiveFeedback", "NegativeFeedback", "RequestingClarificationFromAgent", "PositiveFeedbackToProposal", "NegativeFeedbackToProposal", "RequestForNextStepInPurchase".
    *   **Sinais de Compra:** Se o cliente expressar um desejo claro de prosseguir com a compra, adquirir o produto/serviço, ou perguntar sobre os próximos passos para finalizar (ex: "Quero comprar!", "Como faço o pedido?", "Pode gerar o link de pagamento?", "Vamos fechar negócio!"), classifique como **"RequestForNextStepInPurchase"**.
    *   **Feedback à Proposta:** Se o "TIPO DA ÚLTIMA AÇÃO DO AGENTE" foi "PRESENT_SOLUTION_OFFER":
        *   Se a reação for positiva e indicar acordo com a solução (ex: "Gostei!", "Parece perfeito!", "É isso que eu preciso!"), use **"PositiveFeedbackToProposal"**.
        *   Se a reação for negativa à proposta (ex: "Não acho que isso me atende", "Não é o que eu esperava"), use **"NegativeFeedbackToProposal"**.
        *   Se for uma pergunta específica sobre a proposta, use "Questioning".
        *   Se for uma objeção clara à proposta, use "ExpressingObjection".

   *   **Resposta ao Início do Fechamento:** Se o "TIPO DA ÚLTIMA AÇÃO DO AGENTE" foi "INITIATE_CLOSING":
        *   Se o cliente concordar em prosseguir (ex: "Sim", "Ok", "Pode confirmar", "Vamos lá"), classifique como **"ConfirmingCloseAttempt"**.
        *   Se o cliente recusar (ex: "Não, obrigado", "Ainda não", "Vou pensar mais"), classifique como **"RejectingCloseAttempt"**.
        *   Se o cliente pedir uma correção (ex: "Sim, mas o endereço está errado"), classifique como **"RequestingOrderCorrection"**.
        *   Se levantar uma nova objeção, use "ExpressingObjection".
        *   Se fizer uma pergunta, use "Questioning". 
    
    *   **Resposta à Confirmação de Detalhes:** Se o "TIPO DA ÚLTIMA AÇÃO DO AGENTE" foi "CONFIRM_ORDER_DETAILS":
        *   Se o cliente confirmar final (ex: "Sim, tudo certo", "Confirmo", "Pode finalizar"), classifique como **"FinalOrderConfirmation"**.
        *   Se pedir correção: **"RequestingOrderCorrection"**.
        *   Se recusar/desistir: **"RejectingCloseAttempt"**.
        *   Outros casos: "ExpressingObjection", "Questioning", etc.       

 *     **Resposta à Solicitação de Correção:** Se o "TIPO DA ÚLTIMA AÇÃO DO AGENTE" foi "HANDLE_CLOSING_CORRECTION":
        *   Se o cliente fornecer os detalhes da correção (ex: "O CEP é 99999-000", "Mude a quantidade para 2"), classifique como **"ProvidingCorrectionDetails"**.
        *   Se ele disser que não precisa mais corrigir ou confirmar, use "ConfirmingCloseAttempt" ou "FinalOrderConfirmation".
        *   Se ele recusar, use "RejectingCloseAttempt".
        *   Outros casos: "Questioning", "ExpressingObjection", etc.                
        
2.  **`initially_extracted_questions`**: (Como antes) Identifique TODAS as perguntas explícitas. `question_text`.

3.  **`extracted_objections`**: Identifique quaisquer objeções claras na "ÚLTIMA MENSAGEM DO CLIENTE".
    *   Para cada objeção, forneça o `objection_text`.
    *   **IMPORTANTE**: Capture a frase ou sentenças que *melhor representam a preocupação central do cliente*. Se a objeção for expressa através de uma pergunta seguida de uma afirmação (ex: "Isso é muito caro? Não sei se consigo pagar."), capture a essência completa (ex: "Isso é muito caro? Não sei se consigo pagar." ou "Preço muito caro, não sei se consigo pagar."). Se for uma declaração direta (ex: "O prazo de entrega é muito longo."), capture essa declaração. Tente ser conciso, mas completo.

4.  **`extracted_needs_or_pains`**: (Como antes) Identifique necessidades ou dores. `text` e `type`.

5.  **`analysis_of_response_to_agent_action`** (Objeto `PendingAgentActionResponseAnalysis`):
    *   Avalie como a "ÚLTIMA MENSAGEM DO CLIENTE" se relaciona com a "ÚLTIMA AÇÃO DO AGENTE". **Foque em se o cliente abordou diretamente o ponto principal ou pergunta feita pelo agente.**
    *   `user_response_to_agent_action`: Escolha UM dos seguintes:
        *   "answered_clearly": O cliente respondeu direta e completamente à pergunta/ponto principal do agente.
        *   "partially_answered": O cliente mencionou o ponto do agente, mas de forma incompleta, evasiva, ou adicionou outros pontos não relacionados imediatamente.
        *   "ignored_agent_action": O cliente NÃO abordou o ponto/pergunta principal do agente e mudou de assunto ou fez algo completamente diferente.
        *   "acknowledged_action": O cliente apenas reconheceu a declaração do agente (ex: "ok", "entendi") sem adicionar informação ou responder a uma pergunta implícita.
        *   "not_applicable": Se a ação do agente não esperava uma resposta direta.

6.  **`reaction_to_solution_presentation`** (Objeto `ReactionToPresentation`):
    *   **PREENCHA SOMENTE SE "TIPO DA ÚLTIMA AÇÃO DO AGENTE" for "PRESENT_SOLUTION_OFFER".** Caso contrário, use o default com `reaction_type: "not_applicable"`.
    *   `reaction_type`: Classifique a reação do cliente à apresentação. Valores: "positive_interest", "specific_question", "new_objection_to_solution", "neutral_or_vague", "off_topic_or_unrelated".
    *   `details`: Se "specific_question" ou "new_objection_to_solution", forneça o texto da pergunta/objeção.

7.  **`objection_status_after_rebuttal`** (Objeto `ObjectionAfterRebuttalStatus`):
    *   **PREENCHA SOMENTE SE "TIPO DA ÚLTIMA AÇÃO DO AGENTE" for "GENERATE_REBUTTAL".** Caso contrário, use o default com `status: "not_applicable"`.
    *   `original_objection_text_handled`: Preencha com o valor de "{original_objection_text_if_rebuttal}" fornecido no contexto.
    *   `status`: Avalie o status da objeção original após o rebuttal do agente. Valores: "appears_resolved", "still_persists", "new_objection_raised", "unclear_still_evaluating", "changed_topic".
    *   `new_objection_text`: Se `status` for "new_objection_raised", forneça o texto da nova objeção.

8.  **`is_primarily_vague_statement`**: (Como antes)
9.  **`is_primarily_off_topic`**: (Como antes)
10. **`correction_details_text`**: Se `overall_intent` for "ProvidingCorrectionDetails", extraia o texto específico que o usuário forneceu como correção. Caso contrário, deixe como `null`.

**Instruções Cruciais:**
*   Seja preciso. Se um campo de lista não tiver itens, retorne `[]`.
*   Preencha `reaction_to_solution_presentation` e `objection_status_after_rebuttal` APENAS quando o "TIPO DA ÚLTIMA AÇÃO DO AGENTE" for relevante.

Responda APENAS com o objeto JSON formatado de acordo com o schema `InitialUserInputAnalysis`.
"""


async def initial_input_extraction_sub_step(
    last_user_message_text: str,
    # Modificar para aceitar o objeto PendingAgentAction completo
    last_agent_action_obj: Optional[PendingAgentAction],
    recent_chat_history_str: str,
    llm_fast: BaseChatModel,
) -> Optional[InitialUserInputAnalysis]:
    """
    Performs the initial LLM call to extract structured information from user input.

    Uses the `PROMPT_INITIAL_EXTRACTION` template to guide the LLM. Extracts
    overall intent, potential questions/objections/needs/pains, analyzes the
    response relative to the agent's last action, and assesses reactions to
    presentations or rebuttals if applicable.

    Args:
        last_user_message_text: The text content of the user's latest message.
        last_agent_action_obj: The PendingAgentAction dictionary representing
                               the agent's last action, or None.
        recent_chat_history_str: Formatted string of recent conversation history.
        llm_fast: The language model instance designated for faster tasks.

    Returns:
        An InitialUserInputAnalysis object containing the extracted information,
        or None if the LLM call or parsing fails.
    """
    node_name = "initial_input_extraction_sub_step"
    logger.info(f"[{node_name}] Starting initial input extraction...")

    last_agent_action_text = "N/A - Início da conversa"
    last_agent_action_type_str = "N/A"
    original_objection_text_if_rebuttal_str = "N/A"

    if last_agent_action_obj:
        last_agent_action_text = last_agent_action_obj.get(
            "action_generation_text", "N/A"
        )
        last_agent_action_type_str = last_agent_action_obj.get("action_type", "N/A")
        if last_agent_action_type_str == "GENERATE_REBUTTAL":
            # Assumindo que 'details' contém 'objection_text_to_address'
            original_objection_text_if_rebuttal_str = last_agent_action_obj.get(
                "details", {}
            ).get("objection_text_to_address", "N/A")

    prompt_values = {
        "last_user_message_text": last_user_message_text,
        "last_agent_action_text": last_agent_action_text,
        "last_agent_action_type": last_agent_action_type_str,  # NOVO
        "original_objection_text_if_rebuttal": original_objection_text_if_rebuttal_str,  # NOVO
        "recent_chat_history": recent_chat_history_str,
    }

    analysis_object = await _call_structured_llm(
        llm=llm_fast,
        prompt_template_str=PROMPT_INITIAL_EXTRACTION,  # Usar o prompt atualizado
        prompt_values=prompt_values,
        output_schema=InitialUserInputAnalysis,  # Schema de saída
        node_name_for_logging=node_name,
    )

    if analysis_object:
        logger.info(
            f"[{node_name}] Initial extraction successful. Intent: {analysis_object.overall_intent}"
        )
        if (
            analysis_object.reaction_to_solution_presentation
            and analysis_object.reaction_to_solution_presentation.reaction_type
            != "not_applicable"
        ):
            logger.info(
                f"    Reaction to presentation: {analysis_object.reaction_to_solution_presentation.reaction_type}"
            )
        if (
            analysis_object.objection_status_after_rebuttal
            and analysis_object.objection_status_after_rebuttal.status
            != "not_applicable"
        ):
            logger.info(
                f"    Objection status after rebuttal: {analysis_object.objection_status_after_rebuttal.status}"
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
    Uses an LLM to check if a new question is a semantic repetition of a logged one.

    Args:
        new_question_text: The text of the newly extracted question.
        logged_question_core_text: The core text of a question from the log.
        llm_fast: The language model instance for the check.

    Returns:
        True if the LLM determines it's a semantic repetition, False otherwise
        (including cases where the LLM call fails or the logged text is empty).
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
    Analyzes extracted questions for repetition against a log using an LLM.

    Iterates through questions extracted by the initial step. For each, it
    compares against entries in the customer question log (most recent first)
    using `check_single_repetition_with_llm`. Populates the final
    `ExtractedQuestionAnalysis` object with repetition status and details
    about the original question/answer if a repetition is found.

    Args:
        initially_extracted_questions: List of questions from initial analysis.
        customer_question_log: The existing log of questions asked previously.
        llm_fast: The language model instance for repetition checks.
        current_turn_number: The current turn number, used to avoid self-comparison.

    Returns:
        A list of ExtractedQuestionAnalysis objects, one for each input question,
        with repetition details populated.
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
    Processes the user's input message to extract structured information.

    This node orchestrates the input analysis process:
    1. Performs initial extraction of intent, entities (questions, objections,
       needs, pains), and contextual reactions using an LLM.
    2. Analyzes extracted questions for semantic repetition against the
       conversation history using another LLM call per question/log entry pair.
    3. Combines the results into a final `UserInputAnalysisOutput` object.
    4. Returns the analysis result in the state delta under the key
       'user_input_analysis_result' for the StateUpdaterNode to consume.

    Args:
        state: The current conversation state dictionary. Requires keys like
               'current_user_input_text', 'messages', 'last_agent_action',
               'customer_question_log', 'current_turn_number'.
        config: The graph configuration dictionary, expected to contain the
                'llm_fast_instance' under the 'configurable' key.

    Returns:
        A dictionary containing the state update:
            - 'user_input_analysis_result': A dictionary representation of the
              `UserInputAnalysisOutput` object, or None if processing fails.
            - 'last_processing_error': An error message if a critical step fails.
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
    last_agent_action_obj: Optional[PendingAgentAction] = state.get("last_agent_action")
    raw_messages_history: List[BaseMessage] = state.get("messages", [])
    recent_chat_history_str = _format_recent_chat_history(
        raw_messages_history, limit=RECENT_HISTORY_LIMIT
    )

    # 1. Extração Inicial
    initial_analysis = await initial_input_extraction_sub_step(
        last_user_message_text=last_user_message_text,
        last_agent_action_obj=last_agent_action_obj,  # Passar o objeto
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
        reaction_to_solution_presentation=initial_analysis.reaction_to_solution_presentation,
        objection_status_after_rebuttal=initial_analysis.objection_status_after_rebuttal,
        extracted_questions=updated_questions_with_repetition_info,
        extracted_objections=initial_analysis.extracted_objections,
        extracted_needs_or_pains=initial_analysis.extracted_needs_or_pains,
        analysis_of_response_to_agent_action=initial_analysis.analysis_of_response_to_agent_action,
        is_primarily_vague_statement=initial_analysis.is_primarily_vague_statement,
        is_primarily_off_topic=initial_analysis.is_primarily_off_topic,
        correction_details_text=initial_analysis.correction_details_text,
    )

    logger.info(
        f"[{node_name}] Final user input analysis complete. Intent: {final_analysis.overall_intent}, Questions: {len(final_analysis.extracted_questions)}"
    )
    if final_analysis.extracted_questions:
        for q_idx, q_info in enumerate(final_analysis.extracted_questions):
            logger.debug(
                f"  Q{q_idx+1}: '{q_info.question_text[:50]}...' Repetition: {q_info.is_repetition} (Original Turn: {q_info.original_question_turn}, Original Answer: {q_info.status_of_original_answer})"
            )
    if final_analysis.correction_details_text:
        logger.debug(
            f"  Correction Details Text: '{final_analysis.correction_details_text[:100]}...'"
        )

    # Retorna o resultado para ser adicionado ao estado pelo LangGraph
    # O StateUpdaterNode usará state.get("user_input_analysis_result")
    return {"user_input_analysis_result": final_analysis.model_dump()}
