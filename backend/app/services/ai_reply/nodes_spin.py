# backend/app/services/ai_reply/nodes_spin.py

from typing import Dict, Any, List, Optional
from loguru import logger
import json

# Import State and Constants
from .graph_state import (
    ConversationState,
    CompanyProfileSchema,
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
    Generates a specific SPIN question, potentially linking it to the previous
    user response to make the conversation flow more naturally. Updates
    'last_spin_question_type'.

    Args:
        state: Requires 'messages', 'company_profile', 'spin_question_type'.
        config: Requires 'llm_primary'.

    Returns:
        Dict with 'generation', 'messages', and updated 'last_spin_question_type'.
    """
    node_name = "generate_spin_question_node"
    logger.info(f"--- Starting Node: {node_name} (SPIN Subgraph) ---")
    # logger.debug(f"Recieved state: {state}") # Keep for debugging if needed

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

    logger.debug(f"[{node_name}] Generating SPIN question of type: {spin_type}")

    spin_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas conversacional e especialista na metodologia SPIN Selling.
Sua tarefa ATUAL é fazer UMA ÚNICA pergunta do tipo '{spin_type}' que seja relevante e flua naturalmente na conversa.

Instruções:
1.  **Conecte-se (Opcional):** Se apropriado, comece com uma frase curta que reconheça ou se conecte à ÚLTIMA MENSAGEM DO CLIENTE (ex: "Entendido.", "Interessante o que você disse sobre X...", "Com base nisso então,"). NÃO recapitule longamente.
2.  **Transição Suave:** Use uma frase de transição se necessário (ex: "Isso me leva a perguntar...", "Para entender melhor...", "Pensando nisso,").
3.  **Gere a Pergunta SPIN:** Formule UMA pergunta clara e aberta do tipo '{spin_type}'.
4.  **Seja Conciso:** A resposta final (conexão + transição + pergunta) deve ser natural e não muito longa.
5.  **Foco na Pergunta:** O objetivo principal é obter a informação através da pergunta '{spin_type}'.

PERFIL DA EMPRESA (Contexto): Nome: {company_name}, Descrição: {business_description}, Ofertas: {offering_summary}
HISTÓRICO (Recente):
{chat_history}

Instrução Final: Gere a resposta contendo a pergunta '{spin_type}', seguindo as diretrizes acima.""",
            ),
        ]
    )

    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(messages[-6:])
        ]
    )
    parser = StrOutputParser()
    chain = spin_prompt_template | llm_instance | parser

    try:
        offerings = profile_dict.get("offering_overview", [])
        offering_summary = (
            ", ".join([o.get("name", "?") for o in offerings[:3]])
            if offerings
            else "N/A"
        )

        generated_response = await chain.ainvoke(
            {
                "spin_type": spin_type,
                "company_name": profile_dict.get("company_name", "N/A"),
                "business_description": profile_dict.get("business_description", "N/A"),
                "offering_summary": offering_summary,
                "chat_history": formatted_history if formatted_history else "N/A",
            }
        )
        generated_response = generated_response.strip()

        if not generated_response or len(generated_response) < 5:
            logger.warning(
                f"[{node_name}] LLM generated potentially invalid response: '{generated_response}'. Using fallback."
            )
            raise ValueError("LLM response too short or empty.")

        logger.info(
            f"[{node_name}] Generated SPIN response/question: '{generated_response}'"
        )
        ai_message = AIMessage(content=generated_response)

        return {
            "generation": generated_response,
            "messages": [ai_message],
            "last_spin_question_type": spin_type,
            "error": None,
        }
    except Exception as e:
        logger.exception(f"[{node_name}] Error generating SPIN question/response: {e}")
        fallback_text = ""
        if spin_type == SPIN_TYPE_PROBLEM:
            fallback_text = "Quais desafios você tem encontrado?"
        elif spin_type == SPIN_TYPE_IMPLICATION:
            fallback_text = "E qual o impacto disso?"
        elif spin_type == SPIN_TYPE_NEED_PAYOFF:
            fallback_text = "Como resolver isso ajudaria?"
        else:
            fallback_text = "Pode me contar mais sobre sua situação?"

        fallback_response = AIMessage(content=fallback_text)
        return {
            "generation": fallback_text,
            "messages": [fallback_response],
            "last_spin_question_type": spin_type,
            "error": f"SPIN generation failed: {e}",
        }
