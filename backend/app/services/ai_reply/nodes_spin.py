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
        BaseMessage,
        AIMessage,
        HumanMessage,
        SystemMessage,
    )
    from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
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


from pydantic import BaseModel, Field


# --- Pydantic Schema for SPIN Analysis Output ---
class SpinAnalysisOutput(BaseModel):
    """Structured output for SPIN history analysis."""

    problem_mentioned: bool = Field(
        ...,
        description="True if the customer mentioned any problem, pain, difficulty, or dissatisfaction in the recent history.",
    )
    need_expressed: bool = Field(
        ...,
        description="True if the customer explicitly mentioned a need, goal, objective, or desire for improvement.",
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
        logger.error(f"[{node_name}] LLM instance not found.")
        return {
            "problem_mentioned": False,
            "need_expressed": False,
            "error": "Analysis failed: LLM unavailable.",
        }
    if not messages or len(messages) < 2:
        logger.warning(
            f"[{node_name}] Not enough message history for analysis. Defaulting flags."
        )
        return {"problem_mentioned": False, "need_expressed": False}

    history_to_analyze = messages[-6:]  # Use recent history
    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(history_to_analyze)
        ]
    )

    logger.debug(f"[{node_name}] Analyzing history:\n{formatted_history}")

    # --- Prompt de Análise (Simplificado) ---
    analysis_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um analista de conversas de vendas. Sua tarefa é ler o histórico da conversa fornecido e determinar se o **Cliente** mencionou explicitamente algum **problema/dificuldade/dor** ou alguma **necessidade/objetivo/desejo**.

HISTÓRICO DA CONVERSA (Mais recentes primeiro):
{chat_history}

Determine se um problema foi mencionado e se uma necessidade foi expressa.""",
            ),
            # No human message needed, system prompt contains full instruction
        ]
    )

    # --- Cria LLM Estruturado ---
    structured_llm = llm_fast_instance.with_structured_output(SpinAnalysisOutput)

    try:
        logger.debug(f"[{node_name}] Invoking structured analysis chain...")
        # Invoca o LLM estruturado com o prompt formatado
        analysis_result: SpinAnalysisOutput = await structured_llm.ainvoke(
            analysis_prompt_template.format_messages(
                chat_history=formatted_history if formatted_history else "N/A"
            )
        )
        logger.info(f"[{node_name}] Structured analysis result: {analysis_result}")

        # Extrai valores do objeto Pydantic (já validados)
        return {
            "problem_mentioned": analysis_result.problem_mentioned,
            "need_expressed": analysis_result.need_expressed,
            "error": None,  # Indica sucesso
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error during structured LLM analysis: {e}")
        # Fallback seguro
        return {
            "problem_mentioned": False,
            "need_expressed": False,
            "error": f"Analysis failed: {e}",
        }


# ------------------------------------------------------------------------------


async def select_spin_question_type_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Selects the next type of SPIN question to ask OR signals completion by setting
    'explicit_need_identified' to True and 'spin_question_type' to None.

    Uses the analysis results ('problem_mentioned', 'need_expressed') and the
    type of the last question asked by the agent ('last_spin_question_type').

    Args:
        state: The current conversation state.
        config: The graph configuration.

    Returns:
        A dictionary containing the selected 'spin_question_type' (str or None)
        and the boolean flag 'explicit_need_identified'.
    """
    node_name = "select_spin_question_type_node"
    logger.info(f"--- Starting Node: {node_name} (SPIN Subgraph) ---")
    logger.debug(f"Recieved state: {state}")
    problem_mentioned = state.get("problem_mentioned", False)
    need_expressed = state.get("need_expressed", False)
    last_question_type = state.get(
        "last_spin_question_type"
    )  # O que perguntamos ANTES desta execução
    analysis_error = state.get("error")

    next_spin_type: Optional[str] = None
    explicit_need_identified_flag: bool = False

    if analysis_error and "Analysis failed" in analysis_error:
        logger.warning(
            f"[{node_name}] Analysis failed. Defaulting to Problem question."
        )
        next_spin_type = SPIN_TYPE_PROBLEM
    else:
        # --- Lógica de Progressão SPIN Refinada ---

        # 1. Prioridade Máxima: Se a ÚLTIMA pergunta foi NeedPayoff e o user expressou necessidade AGORA: FIM DO SPIN
        if last_question_type == SPIN_TYPE_NEED_PAYOFF and need_expressed:
            logger.info(
                f"[{node_name}] Explicit need identified after Need-Payoff. Ending SPIN."
            )
            explicit_need_identified_flag = True
            next_spin_type = None  # Sinaliza fim

        # 2. Se o user expressou necessidade AGORA (e não estamos no caso acima): Pergunta NeedPayoff
        elif need_expressed:
            logger.debug(
                f"[{node_name}] Need expressed by user. Moving to Need-Payoff."
            )
            next_spin_type = SPIN_TYPE_NEED_PAYOFF

        # 3. Se a ÚLTIMA pergunta foi Implication e problema foi mencionado AGORA: Pergunta NeedPayoff
        elif last_question_type == SPIN_TYPE_IMPLICATION and problem_mentioned:
            logger.debug(
                f"[{node_name}] After Implication (resonated). Moving to Need-Payoff."
            )
            next_spin_type = SPIN_TYPE_NEED_PAYOFF

        # 4. Se a ÚLTIMA pergunta foi Problem e problema foi mencionado AGORA: Pergunta Implication
        elif last_question_type == SPIN_TYPE_PROBLEM and problem_mentioned:
            logger.debug(
                f"[{node_name}] After Problem (confirmed). Moving to Implication."
            )
            next_spin_type = SPIN_TYPE_IMPLICATION

        # 5. Fallbacks / Continuação Padrão:
        else:
            # Se já fizemos Implication ou NeedPayoff mas não funcionou, voltamos a Problem
            if last_question_type in [SPIN_TYPE_IMPLICATION, SPIN_TYPE_NEED_PAYOFF]:
                logger.debug(
                    f"[{node_name}] Previous Implication/NeedPayoff didn't lead to need. Trying Problem again."
                )
                next_spin_type = SPIN_TYPE_PROBLEM
            # Se a última foi Situation ou Problem (sem confirmação) ou é o início (None)
            else:
                logger.debug(
                    f"[{node_name}] Defaulting to Problem question (Last type: {last_question_type})."
                )
                next_spin_type = SPIN_TYPE_PROBLEM

    logger.info(
        f"[{node_name}] Selected next SPIN type: {next_spin_type}. Explicit need identified: {explicit_need_identified_flag}"
    )

    return {
        "spin_question_type": next_spin_type,
        "explicit_need_identified": explicit_need_identified_flag,
        "error": None if not analysis_error else analysis_error,
    }


# --- generate_spin_question_node (Needs adjustment to update last_spin_question_type) ---
async def generate_spin_question_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a specific SPIN question OR passes through if type is None.
    Updates 'last_spin_question_type' in the returned state with the type
    of question that was actually generated (or None if pass-through).

    Args:
        state: Requires 'messages', 'company_profile', 'spin_question_type'.
        config: Requires 'llm_instance'.

    Returns:
        Dict with 'generation', 'messages', and updated 'last_spin_question_type'.
    """
    node_name = "generate_spin_question_node"
    logger.info(f"--- Starting Node: {node_name} (SPIN Subgraph) ---")
    logger.debug(f"Recieved state: {state}")

    spin_type = state.get("spin_question_type")  # Type selected by previous node

    # If no question type was selected (e.g., SPIN cycle finished), pass through
    if spin_type is None:
        logger.info(
            f"[{node_name}] No SPIN question type selected by previous node. Passing through."
        )
        # Return state update indicating no question was generated THIS turn
        # and keeping the previous last_spin_question_type.
        return {
            "last_spin_question_type": state.get("last_spin_question_type")
        }  # No generation/message change

    # --- Geração da Pergunta (Logic mostly unchanged) ---
    messages = state.get("messages", [])
    profile = state.get("company_profile")
    llm_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )  # Use primary LLM for generation

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
    if not profile:
        return {
            "error": "SPIN generation failed: Missing profile.",
            "last_spin_question_type": state.get("last_spin_question_type"),
        }

    logger.debug(f"[{node_name}] Generating SPIN question of type: {spin_type}")
    spin_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas especialista na metodologia SPIN Selling. Sua tarefa ATUAL é gerar UMA ÚNICA pergunta do tipo '{spin_type}' relevante para a conversa. Baseie-se no HISTÓRICO e PERFIL. NÃO adicione saudações. Gere APENAS a pergunta.
PERFIL DA EMPRESA: Nome: {company_name}, Descrição: {business_description}, Ofertas: {offering_summary}
HISTÓRICO (Recente): {chat_history}
Instrução: Gere uma pergunta '{spin_type}'.""",
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
    spin_chain = spin_prompt_template | llm_instance | parser

    try:
        generated_question = await spin_chain.ainvoke(
            {
                "spin_type": spin_type,
                "company_name": profile.get("company_name", ""),
                "business_description": profile.get("business_description", ""),
                "offering_summary": (
                    ", ".join([o.name for o in profile.offering_overview[:3]])
                    if profile.offering_overview
                    else "N/A"
                ),
                "chat_history": formatted_history if formatted_history else "N/A",
            }
        )
        generated_question = generated_question.strip()
        if not generated_question or not generated_question.endswith("?"):
            logger.warning(
                f"[{node_name}] LLM generated invalid SPIN question: '{generated_question}'. Adding fallback."
            )
            # ... (Fallback logic unchanged) ...
            if spin_type == SPIN_TYPE_PROBLEM:
                generated_question = "Quais são os maiores desafios que você enfrenta atualmente com [área relevante]?"
            elif spin_type == SPIN_TYPE_IMPLICATION:
                generated_question = (
                    "Qual o impacto desses desafios nos seus resultados?"
                )
            elif spin_type == SPIN_TYPE_NEED_PAYOFF:
                generated_question = (
                    "Como resolver [problema] ajudaria a alcançar seus objetivos?"
                )
            else:
                generated_question = (
                    "Pode me contar um pouco mais sobre sua situação atual?"
                )

        logger.info(f"[{node_name}] Generated SPIN question: '{generated_question}'")
        ai_message = AIMessage(content=generated_question)

        # Retorna a geração, a mensagem E atualiza o last_spin_question_type com o tipo GERADO
        return {
            "generation": generated_question,
            "messages": [ai_message],
            "last_spin_question_type": spin_type,  # <-- ATUALIZA O ESTADO
            "error": None,
        }
    except Exception as e:
        logger.exception(f"[{node_name}] Error generating SPIN question: {e}")
        fallback_text = "Poderia me contar um pouco mais sobre isso?"
        fallback_response = AIMessage(content=fallback_text)
        # Retorna fallback e o tipo da última pergunta que TENTOU gerar
        return {
            "generation": fallback_text,
            "messages": [fallback_response],
            "last_spin_question_type": spin_type,  # Mantém o tipo que falhou
            "error": f"SPIN generation failed: {e}",
        }
