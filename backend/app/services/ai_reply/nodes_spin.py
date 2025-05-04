# backend/app/services/ai_reply/nodes_spin.py

from typing import Dict, Any, List, Optional
from loguru import logger
import json
from .prompt_utils import WHATSAPP_MARKDOWN_INSTRUCTIONS

# Import State and Constants
from .graph_state import (
    ConversationState,
    PendingAgentQuestion,
    SPIN_TYPE_SITUATION,
    SPIN_TYPE_PROBLEM,
    SPIN_TYPE_IMPLICATION,
    SPIN_TYPE_NEED_PAYOFF,
    SALES_STAGE_INVESTIGATION,
)

# Import LLM and related components
# Attempt to import essential LangChain components
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
    )
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    # Provide basic fallbacks if LangChain core is not installed
    LANGCHAIN_CORE_AVAILABLE = False
    logger.error(
        "LangChain core components (BaseChatModel, messages, parsers, ChatPromptTemplate) "
        "not found. SPIN nodes will use fallback mechanisms."
    )

    # Define dummy classes to prevent runtime errors if LangChain is missing
    class BaseChatModel:
        pass

    class BaseMessage:
        pass

    class AIMessage:
        content: Optional[str] = None

    class HumanMessage:
        content: Optional[str] = None

    class SystemMessage:
        content: Optional[str] = None

    class StrOutputParser:
        async def ainvoke(self, *args, **kwargs):
            return ""

    class JsonOutputParser:
        async def ainvoke(self, *args, **kwargs):
            return {}

    class ChatPromptTemplate:
        @classmethod
        def from_messages(cls, *args, **kwargs):
            return cls()

        async def ainvoke(self, *args, **kwargs):
            return []


# --- TrustCall Import ---
try:
    from trustcall import create_extractor

    TRUSTCALL_AVAILABLE = True
    logger.info("Successfully imported trustcall.")
except ImportError:
    TRUSTCALL_AVAILABLE = False
    logger.error("trustcall library not found. Analysis node will use fallback.")

    async def create_extractor(*args, **kwargs):
        raise ImportError("trustcall not installed")


from pydantic import BaseModel, Field
from app.api.schemas.company_profile import CompanyProfileSchema


# --- Pydantic Schema for SPIN Analysis Output ---
class SpinAnalysisOutput(BaseModel):
    """Structured output for SPIN history analysis, including summaries."""

    problem_mentioned: bool = Field(
        ...,
        description="True if the customer mentioned any problem, pain, difficulty, or dissatisfaction.",
    )
    problem_summary: Optional[str] = Field(
        None,
        description="A brief summary of the main problem/pain mentioned by the customer, if any.",
    )
    need_expressed: bool = Field(
        ...,
        description="True if the customer explicitly mentioned a need, goal, objective, or desire for improvement.",
    )
    need_summary: Optional[str] = Field(
        None,
        description="A brief summary of the main explicit need/goal mentioned by the customer, if any.",
    )


class SpinGenerationOutput(BaseModel):
    """Structured output for generating SPIN questions."""

    connection_phrase: Optional[str] = Field(
        None,
        description="An optional short phrase connecting to the customer's last message, validating their point or adding context. Should be natural and empathetic. Null or empty if no specific connection is needed.",
    )
    spin_question: str = Field(
        ...,
        description="The specific, clear, and open-ended SPIN question (of the required type) to be asked next.",
    )


# ==============================================================================
# SPIN Subgraph Nodes
# ==============================================================================


async def analyze_history_for_spin_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Uses an LLM with structured output to analyze recent conversation history
    and identify if problems/pains or explicit needs/goals have been mentioned.

    Args:
        state: The current conversation state. Requires 'messages'.
        config: The graph configuration. Requires 'llm_fast_instance'.

    Returns:
        A dictionary containing boolean flags: {'problem_mentioned': bool, 'need_expressed': bool}.
        Returns default False values if analysis fails.
    """
    node_name = "analyze_history_for_spin_node"
    logger.info(f"--- Starting Node: {node_name} (SPIN Subgraph) ---")
    logger.debug(f"Recieved state: {state}")

    messages = state.get("messages", [])
    llm_fast_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validações ---
    if not llm_fast_instance:
        logger.error(f"[{node_name}] Fast LLM instance not found.")
        return {
            "problem_mentioned": False,
            "need_expressed": False,
            "error": "Analysis failed: LLM unavailable.",
        }
    if not messages or len(messages) < 2:
        logger.warning(f"[{node_name}] Not enough message history for analysis.")
        return {"problem_mentioned": False, "need_expressed": False}
    if not TRUSTCALL_AVAILABLE:
        logger.error(
            f"[{node_name}] Trustcall not available. Cannot perform reliable structured extraction."
        )

        return {
            "problem_mentioned": False,
            "need_expressed": False,
            "error": "Analysis failed: Trustcall unavailable.",
        }

    history_to_analyze = messages[-6:]
    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(history_to_analyze)
        ]
    )

    logger.debug(f"[{node_name}] Analyzing history:\n{formatted_history}")

    analysis_prompt = f"""Você é um analista de conversas de vendas. Sua tarefa é ler o histórico da conversa e determinar se o **Cliente** mencionou:
    1.  Algum **problema/dificuldade/dor**?
    2.  Alguma **necessidade/objetivo/desejo** explícito?

    Se um problema for mencionado, forneça um resumo muito breve em 'problem_summary'.
    Se uma necessidade for mencionada, forneça um resumo muito breve em 'need_summary'.
    Se não forem mencionados, use null para os resumos.

    HISTÓRICO DA CONVERSA (Mais recentes primeiro):
    {formatted_history}

    Analise o histórico e extraia as informações solicitadas."""

    try:
        logger.debug(
            f"[{node_name}] Creating trustcall extractor for SpinAnalysisOutput..."
        )
        extractor_agent = create_extractor(
            llm=llm_fast_instance,
            tools=[SpinAnalysisOutput],
            tool_choice=SpinAnalysisOutput.__name__,
        )

        logger.debug(f"[{node_name}] Invoking trustcall extractor agent...")
        result: Dict[str, Any] = await extractor_agent.ainvoke(analysis_prompt)
        logger.debug(f"[{node_name}] Raw result from trustcall: {result}")

        responses = result.get("responses")
        if isinstance(responses, list) and len(responses) > 0:
            extracted_data = responses[0]
            if isinstance(extracted_data, SpinAnalysisOutput):
                logger.info(
                    f"[{node_name}] Trustcall extraction successful: {extracted_data}"
                )

                return {
                    "problem_mentioned": extracted_data.problem_mentioned,
                    "problem_summary": extracted_data.problem_summary,
                    "need_expressed": extracted_data.need_expressed,
                    "need_summary": extracted_data.need_summary,
                    "error": None,
                }
            else:
                logger.error(
                    f"[{node_name}] Trustcall result is not SpinAnalysisOutput. Got: {type(extracted_data)}"
                )
                raise TypeError("Trustcall returned unexpected data type.")
        else:
            logger.error(
                f"[{node_name}] Trustcall failed. Unexpected result structure: {result}"
            )
            raise ValueError(
                "Trustcall extraction failed to produce expected response list."
            )

    except Exception as e:
        logger.exception(f"[{node_name}] Error during trustcall analysis: {e}")
        return {
            # **default_return,  # Retorna valores padrão
            "error": f"Analysis failed: {e}",
        }


# ------------------------------------------------------------------------------


async def select_spin_question_type_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Selects the next SPIN question type OR signals completion.
    Also passes along any identified need/problem summaries.
    """
    node_name = "select_spin_question_type_node"
    logger.info(f"--- Starting Node: {node_name} (SPIN Subgraph) ---")

    problem_mentioned = state.get("problem_mentioned", False)
    need_expressed = state.get("need_expressed", False)

    problem_summary = state.get("problem_summary")
    need_summary = state.get("need_summary")

    last_question_type = state.get("last_spin_question_type")
    analysis_error = state.get("error")

    next_spin_type: Optional[str] = None
    explicit_need_identified_flag: bool = False

    if analysis_error and "Analysis failed" in analysis_error:
        logger.warning(f"[{node_name}] Analysis failed. Defaulting to Problem.")
        next_spin_type = SPIN_TYPE_PROBLEM
        analysis_error = None
    elif last_question_type == SPIN_TYPE_NEED_PAYOFF and need_expressed:
        logger.info(
            f"[{node_name}] Explicit need identified after Need-Payoff. Ending SPIN."
        )
        explicit_need_identified_flag = True
        next_spin_type = None
    elif need_expressed:
        logger.debug(f"[{node_name}] Need expressed. Moving to Need-Payoff.")
        next_spin_type = SPIN_TYPE_NEED_PAYOFF
    elif last_question_type == SPIN_TYPE_IMPLICATION and problem_mentioned:
        logger.debug(
            f"[{node_name}] After Implication (resonated). Moving to Need-Payoff."
        )
        next_spin_type = SPIN_TYPE_NEED_PAYOFF
    elif last_question_type == SPIN_TYPE_PROBLEM and problem_mentioned:
        logger.debug(f"[{node_name}] After Problem (confirmed). Moving to Implication.")
        next_spin_type = SPIN_TYPE_IMPLICATION
    else:
        if last_question_type in [SPIN_TYPE_IMPLICATION, SPIN_TYPE_NEED_PAYOFF]:
            logger.debug(
                f"[{node_name}] Previous Implication/NeedPayoff didn't lead to need. Trying Problem."
            )
            next_spin_type = SPIN_TYPE_PROBLEM
        else:
            logger.debug(
                f"[{node_name}] Defaulting to Problem question (Last type: {last_question_type})."
            )
            next_spin_type = SPIN_TYPE_PROBLEM

    logger.info(
        f"[{node_name}] Selected next SPIN type: {next_spin_type}. Explicit need identified: {explicit_need_identified_flag}"
    )

    output = {
        "spin_question_type": next_spin_type,
        "explicit_need_identified": explicit_need_identified_flag,
        "error": None if not analysis_error else analysis_error,
    }

    if problem_summary:
        output["customer_pain_points"] = [problem_summary]
    if need_summary:
        output["customer_needs"] = [need_summary]

    return output


# --- generate_spin_question_node  ---
async def generate_spin_question_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a specific SPIN question using structured output for connection
    phrase and the question itself, then combines them. Updates 'last_spin_question_type'.

    Args:
        state: Requires 'messages', 'company_profile', 'spin_question_type'.
        config: Requires 'llm_primary_instance'.

    Returns:
        Dict with 'generation', 'messages', and updated 'last_spin_question_type'.
    """
    node_name = "generate_spin_question_node"
    logger.info(f"--- Starting Node: {node_name} (SPIN Subgraph) ---")

    pending_question = state.get("pending_agent_question")
    spin_type = state.get("spin_question_type")
    if spin_type is None:
        logger.info(f"[{node_name}] No SPIN question type selected. Passing through.")
        return {"last_spin_question_type": state.get("last_spin_question_type")}

    messages = state.get("messages", [])
    profile_dict = state.get("company_profile")
    llm_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )

    # --- Validações ---
    if not llm_instance:
        return {
            "error": "SPIN generation failed: LLM unavailable.",
            "last_spin_question_type": state.get("last_spin_question_type"),
        }
    if not messages:
        return {
            "error": "SPIN generation failed: Empty message history.",
            "last_spin_question_type": state.get("last_spin_question_type"),
        }
    if not profile_dict or not isinstance(profile_dict, dict):
        return {
            "error": "SPIN generation failed: Missing profile dict.",
            "last_spin_question_type": state.get("last_spin_question_type"),
        }

    # --- Lógica para Re-perguntar ou Gerar Nova ---
    output_generation: Optional[str] = None
    output_pending_question: Optional[PendingAgentQuestion] = None
    output_error: Optional[str] = None

    # Verifica se há pergunta pendente e se devemos tentar de novo
    if (
        pending_question
        and isinstance(pending_question, dict)
        and pending_question.get("status") == "pending"
    ):
        attempts = pending_question.get("attempts", 1)
        original_question_text = pending_question.get("text")
        original_question_type = pending_question.get("type")
        logger.warning(
            f"[{node_name}] Re-asking pending question (Type: {original_question_type}, Attempt: {attempts}): '{original_question_text}'"
        )

        output_generation = f"Retomando o ponto anterior: {original_question_text}"  # Exemplo simples de re-perguntar

        # >>> IMPORTANTE: Retorna o MESMO objeto pending_question (com attempts já incrementado) <<<
        output_pending_question = pending_question
        output_error = None

    else:
        last_human_message_obj = (
            messages[-1]
            if messages and isinstance(messages[-1], HumanMessage)
            else None
        )
        last_human_message_content = getattr(last_human_message_obj, "content", "")

        logger.debug(f"[{node_name}] Generating SPIN question of type: {spin_type}")
        logger.debug(
            f"[{node_name}] Last human message for context: '{last_human_message_content[:100]}...'"
        )

        # --- Prompt ATUALIZADO para Saída Estruturada ---
        spin_prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Você é um assistente de vendas IA conversacional, especialista em SPIN Selling, com um toque humano e empático.
    Sua tarefa é gerar a PRÓXIMA pergunta da conversa, do tipo '{spin_type}', separando a frase de conexão da pergunta principal.

    **Contexto:**
    Última Mensagem do Cliente: {last_customer_message}
    Tipo de Pergunta SPIN a ser Gerada: {spin_type}

    **Instruções:**
    1.  **Analise a Última Mensagem:** Identifique o tópico/sentimento central (interesse, problema, etc.).
    2.  **Gere a `connection_phrase` (Opcional, mas VALIOSA):**
        *   **Objetivo:** Criar uma ponte natural e agregar valor, mostrando que você entendeu e contextualizou a fala do cliente.
        *   **Como:** Se um tópico claro foi identificado, crie uma frase curta que valide E **adicione um breve insight, contexto ou reforço de valor**.
            *   Exemplo (Interesse em 'Qualificação'): "Realmente, a *qualificação automática* é um desafio comum (ou 'é fundamental') quando se está crescendo."
            *   Exemplo (Problema 'Tempo Gasto'): "Entendo, otimizar esse *tempo gasto* é crucial para liberar sua equipe para tarefas estratégicas."
            *   Exemplo (Problema [Topico X]): "Entendo, o [Topico X] é crucial para [Coisas que o Topico X é crucial]."
        *   **Adapte a Profundidade:** A riqueza da sua conexão deve espelhar a riqueza da mensagem do cliente. Se ele foi detalhado, sua conexão pode ser mais elaborada. Se ele foi muito breve (ex: "sim", "ok"), use uma conexão mínima ("Entendido.", "Ok.") ou deixe nula/vazia.
        *   **Evite Redundância Óbvia:** Não repita exatamente o que o cliente disse nem faça afirmações genéricas demais.
        *   **Seja Natural e Empático:** Evite frases robóticas.
    3.  **Gere a `spin_question` (Obrigatório):**
        *   Formule UMA pergunta clara, aberta e específica do tipo '{spin_type}'.
        *   Conecte-a diretamente ao tópico/sentimento identificado na última mensagem do cliente, se possível.
    4.  **Formatação:** Use formatação WhatsApp sutil dentro das frases, se aplicável. {formatting_instructions}
    5.  **Output:** Responda APENAS com um objeto JSON contendo os campos "connection_phrase" (string opcional ou null) e "spin_question" (string obrigatória).

    PERFIL DA EMPRESA (Contexto): Nome: {company_name}, Descrição: {business_description}, Ofertas: {offering_summary}
    HISTÓRICO (Recente - opcional): {chat_history}

    Instrução Final: Gere o JSON com "connection_phrase" e "spin_question" para o tipo '{spin_type}'.""",
                ),
            ]
        )

        formatted_history = "\n".join(
            [
                f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
                for m in reversed(messages[-6:-1])
            ]
        )

        # --- Cadeia com LLM Estruturado ---
        structured_llm = llm_instance.with_structured_output(SpinGenerationOutput)
        chain = spin_prompt_template | structured_llm

        try:
            offerings = profile_dict.get("offering_overview", [])
            offering_summary = (
                ", ".join([o.get("name", "?") for o in offerings[:3]])
                if offerings
                else "N/A"
            )

            # Invoca a cadeia para obter o objeto estruturado
            structured_result: SpinGenerationOutput = await chain.ainvoke(
                {
                    "spin_type": spin_type,
                    "last_customer_message": (
                        last_human_message_content
                        if last_human_message_content
                        else "N/A"
                    ),
                    "company_name": profile_dict.get("company_name", "N/A"),
                    "business_description": profile_dict.get(
                        "business_description", "N/A"
                    ),
                    "offering_summary": offering_summary,
                    "chat_history": formatted_history if formatted_history else "N/A",
                    "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
                }
            )

            logger.info(
                f"[{node_name}] Structured SPIN generation result: {structured_result}"
            )

            # --- Combina as partes ---
            connection = structured_result.connection_phrase
            question = structured_result.spin_question

            if not question or not question.endswith("?"):
                raise ValueError("Invalid question")

            if connection and connection.strip():
                output_generation = f"{connection.strip()} {question}"
            else:
                output_generation = question

            # >>> IMPORTANTE: Cria um NOVO objeto pending_question com attempts = 1 <<<
            output_pending_question = {
                "text": question,  # A pergunta efetivamente feita
                "type": f"SPIN_{spin_type}",
                "status": "pending",
                "attempts": 1,  # Primeira tentativa desta nova pergunta
            }
            output_error = None

        except Exception as e:
            # ... (Fallback como antes, usando apenas a pergunta fallback) ...
            logger.exception(
                f"[{node_name}] Error generating structured SPIN question/response: {e}"
            )
            fallback_text = ""
            if spin_type == SPIN_TYPE_PROBLEM:
                fallback_text = "Quais desafios você tem encontrado?"
            elif spin_type == SPIN_TYPE_IMPLICATION:
                fallback_text = "E qual o impacto disso?"
            elif spin_type == SPIN_TYPE_NEED_PAYOFF:
                fallback_text = "Como resolver isso ajudaria?"
            else:
                fallback_text = "Pode me contar mais sobre sua situação?"

            output_generation = fallback_text
            if fallback_text.endswith("?"):
                output_pending_question = {
                    "text": fallback_text,
                    "type": f"SPIN_{spin_type}_Fallback",
                    "status": "pending",
                    "attempts": 1,
                }
            output_error = f"SPIN generation failed: {e}"

    if output_generation:
        logger.info(f"[{node_name}] Final question/response: '{output_generation}'")
        ai_message = AIMessage(content=output_generation)
        return {
            "generation": output_generation,
            "messages": [ai_message],
            "last_spin_question_type": spin_type,  # Mantém o tipo que *tentamos* gerar/re-perguntar
            "pending_agent_question": output_pending_question,  # <-- Retorna o objeto correto (novo ou existente)
            "error": output_error,
        }
    else:
        logger.error(f"[{node_name}] Failed to generate or re-ask question.")
        return {"error": "Failed to determine question to ask."}
