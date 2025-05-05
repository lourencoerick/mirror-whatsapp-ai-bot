# backend/app/services/ai_reply/nodes_core.py

import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger
from uuid import UUID
from datetime import datetime, timezone
import pytz

# Import State and Constants
from .graph_state import (
    ConversationState,
    PendingAgentQuestion,
    CustomerQuestionEntry,
    SALES_STAGE_OPENING,
    SALES_STAGE_QUALIFICATION,
    SALES_STAGE_INVESTIGATION,
    SALES_STAGE_PRESENTATION,
    SALES_STAGE_OBJECTION_HANDLING,
    SALES_STAGE_CLOSING,
    SALES_STAGE_FOLLOW_UP,
    SALES_STAGE_UNKNOWN,
)

# --- Imports for RAG Node (moved from graph_nodes.py) ---
try:
    from app.core.embedding_utils import get_embedding

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.error("Embedding utils not found.")

    async def get_embedding(*args, **kwargs):
        return None


try:
    from app.services.repository.knowledge_chunk import search_similar_chunks
    from app.models.knowledge_chunk import KnowledgeChunk

    CHUNK_REPO_AVAILABLE = True
except ImportError:
    CHUNK_REPO_AVAILABLE = False
    logger.error("Knowledge repository not found.")

    async def search_similar_chunks(*args, **kwargs) -> List:
        return []

    class KnowledgeChunk:
        pass  # Dummy class


try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    AsyncSession = None
    async_sessionmaker = None
# --- End RAG Imports ---

# --- Imports for Generate Response Node  ---
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import (
        BaseMessage,
        AIMessage,
        HumanMessage,
    )
    from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    logger.error("LangChain core not found.")

    class BaseChatModel:
        pass

    class BaseMessage:
        pass

    class AIMessage:
        content: Optional[str] = None

    class HumanMessage:
        content: Optional[str] = None  # Dummy class


try:
    from app.services.ai_reply.prompt_builder import build_llm_prompt_messages

    PROMPT_BUILDER_AVAILABLE = True
except ImportError:
    PROMPT_BUILDER_AVAILABLE = False
    logger.error("Prompt builder not found.")

    def build_llm_prompt_messages(*args, **kwargs) -> List[BaseMessage]:
        return []


from app.api.schemas.company_profile import CompanyProfileSchema

from app.services.ai_reply.prompt_utils import WHATSAPP_MARKDOWN_INSTRUCTIONS

# --- End Generate Response Imports ---


# --- Constants ---
RAG_CHUNK_LIMIT = 3
RAG_SIMILARITY_THRESHOLD = 0.5

VALID_SALES_STAGES = [
    SALES_STAGE_OPENING,
    SALES_STAGE_QUALIFICATION,
    SALES_STAGE_INVESTIGATION,
    SALES_STAGE_PRESENTATION,
    SALES_STAGE_OBJECTION_HANDLING,
    SALES_STAGE_CLOSING,
    SALES_STAGE_FOLLOW_UP,
    SALES_STAGE_UNKNOWN,
]
VALID_INTENTS = [
    "Greeting",
    "Question",
    "Statement",
    "Objection",
    "ClosingAttempt",
    "Complaint",
    "Other",
    "Unknown",
    "VagueStatement",
    "Goodbye",
]

from pydantic import BaseModel, Field
from typing import Literal  # Para Literal


# --- Pydantic Schema for Intent/Stage Classification Output ---
class IntentStageClassificationOutput(BaseModel):
    """Structured output for intent and sales stage classification."""

    intent: str = Field(..., description=f"Primary intent. Valid: {VALID_INTENTS}")
    next_sales_stage: str = Field(
        ..., description=f"Recommended next stage. Valid: {VALID_SALES_STAGES}"
    )
    is_problem_statement: bool = Field(
        ...,
        description="True ONLY if the customer is describing a problem/pain point in response to an investigation question, NOT raising an objection to the sale itself.",
    )  # <-- NOVO CAMPO


class ProposedSolutionDetails(BaseModel):
    """Structured output defining the specific solution proposed to the customer."""

    product_name: str = Field(
        ..., description="The name of the main product/service being proposed."
    )
    quantity: Optional[int] = Field(
        ..., description="The quantity being proposed (default to 1 if not specified)."
    )
    price: Optional[float] = Field(
        None,
        description="The total price for the proposed quantity, if known or inferable.",
    )
    price_info: Optional[str] = Field(
        None,
        description="Additional context about the price (e.g., 'per month', 'one-time fee').",
    )
    key_benefit_addressed: Optional[str] = Field(
        None,
        description="The main customer need or pain point this specific proposal addresses.",
    )
    delivery_info: Optional[str] = Field(
        None, description="Relevant delivery or setup information, if applicable."
    )


class AnswerStatusOutput(BaseModel):
    """Structured output analyzing if the user answered the agent's question."""

    answered_status: Literal["YES", "NO", "PARTIAL"] = Field(
        ...,
        description="Did the user's last message adequately answer the agent's pending question? YES, NO, or PARTIAL.",
    )


class TransitionOutput(BaseModel):
    """Structured output for the transition node."""

    transition_text: str = Field(
        ..., description="The full transition text (acknowledgement + question)."
    )
    question_asked: str = Field(
        ..., description="The specific question asked in the transition."
    )
    question_type: str = Field(
        ...,
        description="The type of question asked (e.g., 'Resume_Pending', 'New_Investigation').",
    )


class RepetitionCheckOutput(BaseModel):
    """Structured output analyzing if the user is repeating an unanswered question."""

    is_repeated: bool = Field(
        ...,
        description="Is the current user question semantically similar to a previous one in the history?",
    )
    was_unanswered: bool = Field(
        ...,
        description="If it is repeated, did the agent's response immediately following the *first* instance of that question indicate it couldn't answer (e.g., used fallback phrases)?",
    )


class ExtractedQuestionInfo(BaseModel):
    """Holds info about a single extracted question and its similarity check."""

    extracted_question: str = Field(
        ..., description="The core question extracted, removing introductions."
    )
    is_similar: bool = Field(
        ...,
        description="Is this extracted question semantically similar to any previous unanswered/ignored question?",
    )
    most_similar_previous_question: Optional[str] = Field(
        None,
        description="If similar, the text of the most similar previous question found.",
    )


# --- Pydantic Schema for the Node's Output ---
class MultiQuestionAnalysisOutput(BaseModel):
    """Output containing a list of analyzed questions from the user's message."""

    analyzed_questions: List[ExtractedQuestionInfo] = Field(default_factory=list)


class AnswerCheckOutput(BaseModel):
    """Checks if the agent's response answered the preceding user question."""

    did_answer: bool = Field(
        ...,
        description="Did the agent's response directly and sufficiently answer the user's question?",
    )
    used_fallback: bool = Field(
        ...,
        description="Did the agent's response indicate inability to answer (e.g., 'I don't know', 'contact us')?",
    )


# ==============================================================================
# Core Graph Nodes
# ==============================================================================


async def classify_intent_and_stage_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Uses an LLM with structured output to classify intent, determine the next
    sales stage, and identify if the user is stating a problem vs. objecting.

    Args:
        state: The current conversation state. Requires 'messages'.
        config: The graph configuration. Requires 'llm_fast_instance'.

    Returns:
        A dictionary containing 'intent', 'current_sales_stage', 'classification_details',
        and optionally 'error'.
    """
    node_name = "classify_intent_and_stage_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    llm_fast_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )
    previous_stage = state.get("current_sales_stage")
    explicit_need_identified = state.get("explicit_need_identified", False)

    # --- Validações ---
    if not llm_fast_instance:
        logger.error(f"[{node_name}] LLM instance not found.")
        return {"error": "Classification failed: LLM unavailable."}
    if not messages:
        logger.warning(f"[{node_name}] No messages. Defaulting stage to Opening.")
        return {
            "intent": "Unknown",
            "current_sales_stage": SALES_STAGE_OPENING,
            "error": None,
        }

    history_for_classification = messages[-10:]  # Analisa últimas 10 mensagens
    last_message = history_for_classification[-1]
    # Pega a penúltima mensagem (provável pergunta do agente) para contexto
    previous_agent_message_content = (
        getattr(history_for_classification[-2], "content", "")
        if len(history_for_classification) >= 2
        else ""
    )

    last_message_content = (
        getattr(last_message, "content", "")
        if isinstance(getattr(last_message, "content", ""), str)
        else ""
    )
    if not last_message_content:
        logger.warning(f"[{node_name}] Last message has no text content.")
        return {
            "intent": "Unknown",
            "current_sales_stage": previous_stage or SALES_STAGE_OPENING,
            "error": None,
        }

    logger.debug(
        f"[{node_name}] Classifying message: '{last_message_content[:100]}...'"
    )
    logger.debug(f"[{node_name}] Previous stage: {previous_stage}")
    logger.debug(
        f"[{node_name}] Previous agent msg: '{previous_agent_message_content[:100]}...'"
    )

    # --- Prompt de Classificação (REFINADO) ---
    classification_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um especialista em análise de conversas de vendas (SPIN, etc.). Analise a ÚLTIMA MENSAGEM do cliente no contexto do HISTÓRICO e da ÚLTIMA PERGUNTA DO AGENTE.
Sua tarefa é classificar a INTENÇÃO, determinar o PRÓXIMO ESTÁGIO da venda e identificar se é uma DECLARAÇÃO DE PROBLEMA.

Estágios Válidos: {valid_stages}
Intenções Válidas: {valid_intents}

**Regras de Classificação:**
- **Greeting:** Saudações. -> Próximo Estágio: 'Opening'. `is_problem_statement`: false.
- **Question:** Pergunta direta sobre produto, preço, processo. -> Próximo Estágio: 'Investigation' (ou manter avançado). `is_problem_statement`: false.
- **Statement:** Afirmação, resposta neutra, descrição de situação. -> Próximo Estágio: Geralmente 'Investigation', *MAS* se `explicit_need_identified` for TRUE, então 'Presentation'. `is_problem_statement`: false.
- **Objection:** Cliente expressa barreira CLARA à COMPRA ou ao AVANÇO (preço da *solução*, tempo para *implementar*, valor da *solução*, concorrente, "preciso pensar *sobre a compra*"). -> Próximo Estágio: 'ObjectionHandling'. `is_problem_statement`: false.
- **ClosingAttempt:** Cliente demonstra interesse claro em comprar/prosseguir. -> Próximo Estágio: 'Closing'. `is_problem_statement`: false.
- **Complaint:** Reclamação. -> Próximo Estágio: 'ObjectionHandling'. `is_problem_statement`: false.
- **Other/Unknown:** Não se encaixa. -> Próximo Estágio: Manter ou 'Unknown'. `is_problem_statement`: false.
- **VagueStatement:** Cliente expressa dúvida, incerteza, ou necessidade de pensar **sem especificar o motivo ou o ponto de dúvida**. Exemplos: "preciso pensar melhor", "não sei...", "não entendi direito essa parte", "parece complicado". -> Próximo Estágio: Manter o estágio atual ou 'Investigation'. `is_problem_statement`: false.
- **Goodbye:** Cliente indica explicitamente que quer encerrar a conversa, não tem mais interesse, ou se despede. Exemplos: "obrigado, por enquanto é só", "não tenho interesse", "tchau", "até logo". -> Próximo Estágio: Manter o atual ou 'Unknown'. 
- **CASO ESPECIAL - Pós-Confirmação/Processamento:** Se o `current_closing_status` for 'ORDER_PROCESSED' ou 'FINAL_CONFIRMED' (indicando que o agente acabou de confirmar um pedido ou próximo passo), E a 'ÚLTIMA MENSAGEM DO CLIENTE' contiver principalmente agradecimentos, confirmação dessa ação, ou apenas reiterações de dúvidas/preocupações antigas (sem novas objeções fortes ou perguntas urgentes), então classifique o `intent` como **'Goodbye'**. O objetivo é reconhecer o fim natural da interação principal.

**IMPORTANTE - Declaração de Problema:**
- Se a 'ÚLTIMA PERGUNTA DO AGENTE' foi uma pergunta de Situação ou Problema (ex: "Quais desafios você enfrenta?", "Como você faz X hoje?"), E a 'ÚLTIMA MENSAGEM DO CLIENTE' descreve uma dificuldade, dor, ou insatisfação (ex: "gasto muito tempo", "é difícil fazer Y", "não consigo Z"), então:
    - `intent` deve ser 'Statement'.
    - `next_sales_stage` deve ser 'Investigation' (para continuar investigando com Implicação/Need-Payoff).
    - `is_problem_statement` deve ser **true**.
- **NÃO confunda uma declaração de problema com uma objeção.** Objeção é resistência à *venda*, declaração de problema é descrição da *situação atual* do cliente.
- **Diferenciação:** NÃO confunda `VagueStatement` com `Objection` (que tem uma barreira clara) ou `Question` (que pergunta algo específico)

HISTÓRICO DA CONVERSA: {chat_history}
ESTÁGIO ANTERIOR: {previous_stage}
FLAG NECESSIDADE EXPLÍCITA IDENTIFICADA: {explicit_need_identified}
ÚLTIMA PERGUNTA DO AGENTE (Aproximada): {previous_agent_message}
ÚLTIMA MENSAGEM DO CLIENTE: {last_message}

Responda APENAS com um objeto JSON contendo "intent", "next_sales_stage", e "is_problem_statement".""",
            ),
        ]
    )

    # Formata o histórico
    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(
                history_for_classification[:-1]
            )  # Exclui a última msg do cliente daqui
        ]
    )

    # --- Cria LLM Estruturado ---
    # Usando with_structured_output para consistência (assumindo llm_fast_instance suporta)
    structured_llm = llm_fast_instance.with_structured_output(
        IntentStageClassificationOutput
    )

    try:
        logger.debug(f"[{node_name}] Invoking structured classification chain...")
        # Preenche o prompt
        prompt_filled = classification_prompt_template.format_messages(
            valid_stages=", ".join(VALID_SALES_STAGES),
            valid_intents=", ".join(VALID_INTENTS),
            chat_history=formatted_history or "N/A",
            previous_stage=previous_stage or "None",
            previous_agent_message=previous_agent_message_content or "N/A",
            last_message=last_message_content,
            explicit_need_identified=str(explicit_need_identified).upper(),
        )
        # Invoca o LLM
        classification_result: IntentStageClassificationOutput = (
            await structured_llm.ainvoke(prompt_filled)
        )
        logger.info(
            f"[{node_name}] Structured classification result: {classification_result}"
        )

        # --- Validação Pós-LLM (Opcional, mas útil) ---
        intent = classification_result.intent
        next_stage = classification_result.next_sales_stage
        is_problem_stmt = classification_result.is_problem_statement

        # Correção: Se for uma declaração de problema, garantir que vá para Investigation
        if is_problem_stmt:
            intent = "Statement"  # Garante que a intenção seja Statement
            next_stage = SALES_STAGE_INVESTIGATION  # Força a continuar investigando
            logger.info(
                f"[{node_name}] Identified as Problem Statement. Forcing Stage to Investigation."
            )

        # Validar se os valores estão na lista permitida (redundante com Pydantic, mas seguro)
        if intent not in VALID_INTENTS:
            intent = "Unknown"
        if next_stage not in VALID_SALES_STAGES:
            next_stage = previous_stage or SALES_STAGE_UNKNOWN

        return {
            "intent": intent,
            "current_sales_stage": next_stage,
            "classification_details": classification_result.model_dump(),  # Guarda detalhes completos
            "error": None,
        }

    except Exception as e:
        logger.exception(
            f"[{node_name}] Error during structured LLM classification: {e}"
        )
        return {
            "intent": "Unknown",
            "current_sales_stage": previous_stage or SALES_STAGE_UNKNOWN,
            "classification_details": {"error": str(e)},
            "error": f"Classification failed: {e}",
        }


async def check_pending_answer_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Checks if the latest user message answers the agent's pending question.
    Updates the status of 'pending_agent_question'. Does NOT generate a response.

    Args:
        state: Requires 'messages', 'pending_agent_question'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with potentially updated 'pending_agent_question'.
    """
    node_name = "check_pending_answer_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    pending_question = state.get("pending_agent_question")
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )
    max_attempts = 3  # Número máximo de tentativas antes de ignorar

    # --- Validações e Condições de Saída ---
    if not pending_question or not isinstance(pending_question, dict):
        logger.debug(f"[{node_name}] No pending agent question found. Skipping.")
        return {}  # Nada a fazer
    if pending_question.get("status") != "pending":
        logger.debug(
            f"[{node_name}] Pending question status is not 'pending' ({pending_question.get('status')}). Skipping."
        )
        return {
            "pending_agent_question": pending_question
        }  # Retorna o estado inalterado
    if not llm_fast:
        logger.error(f"[{node_name}] LLM unavailable. Cannot check answer status.")
        # Mantém pendente, mas loga erro? Ou ignora? Vamos manter pendente por ora.
        return {
            "pending_agent_question": pending_question,
            "error": "Pending check failed: LLM unavailable.",
        }
    if not messages or not isinstance(messages[-1], HumanMessage):
        logger.warning(
            f"[{node_name}] Last message not from user. Cannot check answer status."
        )
        # Mantém pendente se não podemos analisar a resposta
        return {"pending_agent_question": pending_question}

    last_user_message = messages[-1].content
    question_text = pending_question.get("text")
    attempts = pending_question.get("attempts", 0)  # Pega tentativas atuais

    logger.debug(f"[{node_name}] Checking if user response answers: '{question_text}'")
    logger.debug(f"[{node_name}] User response: '{last_user_message[:100]}...'")
    logger.debug(f"[{node_name}] Current attempts: {attempts}")

    # --- Prompt para Análise da Resposta ---
    analysis_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um analista de conversas. O agente fez uma pergunta específica e o cliente respondeu.
Avalie se a RESPOSTA DO CLIENTE responde adequadamente à PERGUNTA DO AGENTE.

PERGUNTA DO AGENTE: {agent_question}
RESPOSTA DO CLIENTE: {customer_response}

Determine o status da resposta:
- YES: A resposta do cliente aborda diretamente e fornece a informação solicitada pela pergunta do agente.
- NO: A resposta do cliente ignora completamente a pergunta do agente ou muda de assunto.
- PARTIAL: A resposta do cliente toca no assunto da pergunta, mas é incompleta, vaga, ou evasiva.

Responda APENAS com um objeto JSON seguindo o schema AnswerStatusOutput.""",
            ),
        ]
    )

    # --- Cadeia com LLM Estruturado ---
    structured_llm = llm_fast.with_structured_output(AnswerStatusOutput)
    chain = analysis_prompt_template | structured_llm

    try:
        analysis_result: AnswerStatusOutput = await chain.ainvoke(
            {
                "agent_question": question_text,
                "customer_response": last_user_message,
            }
        )
        logger.info(
            f"[{node_name}] Answer status analysis result: {analysis_result.answered_status}"
        )

        # --- Atualiza Status da Pergunta Pendente ---
        new_pending_status = pending_question.copy()  # Cria cópia para modificar

        if analysis_result.answered_status == "YES":
            new_pending_status["status"] = "answered"
            logger.info(f"[{node_name}] Pending question marked as 'answered'.")
            # Retorna None para limpar a pergunta pendente do estado principal
            return {"pending_agent_question": None}
        else:  # NO ou PARTIAL
            new_attempts = attempts + 1
            new_pending_status["attempts"] = new_attempts
            if new_attempts >= max_attempts:
                new_pending_status["status"] = "ignored"
                logger.warning(
                    f"[{node_name}] Pending question reached max attempts ({max_attempts}). Marked as 'ignored'."
                )
                # Retorna None para limpar a pergunta pendente do estado principal
                return {"pending_agent_question": None}
            else:
                # Mantém status 'pending' e incrementa tentativas
                new_pending_status["status"] = "pending"
                logger.info(
                    f"[{node_name}] Pending question remains 'pending'. Attempts incremented to {new_attempts}."
                )
                return {"pending_agent_question": new_pending_status}

    except Exception as e:
        logger.exception(f"[{node_name}] Error during answer status analysis: {e}")
        # Em caso de erro, mantém a pergunta como pendente sem incrementar tentativas?
        # Ou incrementa para evitar loop? Vamos incrementar por segurança.
        new_pending_status = pending_question.copy()
        new_pending_status["attempts"] = attempts + 1
        if new_pending_status["attempts"] >= max_attempts:
            new_pending_status["status"] = "ignored"
            logger.warning(
                f"[{node_name}] Pending question reached max attempts due to error. Marked 'ignored'."
            )
            return {
                "pending_agent_question": None,
                "error": f"Pending check failed: {e}",
            }
        else:
            logger.error(
                f"[{node_name}] Analysis failed. Keeping question pending, attempts {new_pending_status['attempts']}."
            )
            return {
                "pending_agent_question": new_pending_status,
                "error": f"Pending check failed: {e}",
            }


async def update_question_log_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Extracts one or more questions from the last user message, checks each for
    repetition against unanswered/ignored questions in the log, updates the main log,
    and populates the 'current_questions' state field.

    Args:
        state: Requires 'messages', 'customer_question_log', 'loop_count', 'intent'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with updated 'customer_question_log' and 'current_questions'.
    """
    node_name = "update_question_log_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    current_log: List[CustomerQuestionEntry] = [
        entry.copy() for entry in state.get("customer_question_log", [])
    ]
    current_turn = state.get("loop_count", 0)
    intent = state.get("intent")  # Usado para decidir se processa
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )
    max_attempts = 3

    # --- Validações ---
    if not llm_fast:
        logger.error(f"[{node_name}] LLM unavailable.")
        # Retorna estado inalterado, mas sem current_questions
        return {
            "customer_question_log": state.get("customer_question_log", []),
            "current_questions": None,
        }
    if not messages or not isinstance(messages[-1], HumanMessage):
        logger.debug(f"[{node_name}] Last message not from user or no messages.")
        return {"customer_question_log": current_log, "current_questions": None}

    # Processa apenas se o intent sugere uma pergunta ou algo que possa conter uma
    # (Question, VAGUE_STATEMENT, talvez Statement dependendo da complexidade desejada)
    # Por simplicidade, vamos focar em 'Question' por enquanto.
    if intent != "Question":
        logger.debug(
            f"[{node_name}] Intent is '{intent}'. Skipping question extraction."
        )
        return {"customer_question_log": current_log, "current_questions": None}

    current_message_original_text = messages[-1].content
    logger.debug(
        f"[{node_name}] Processing current message for questions: '{current_message_original_text[:100]}...'"
    )

    # --- Extrair Perguntas e Verificar Similaridade ---
    extracted_questions_info: List[ExtractedQuestionInfo] = []
    previous_unanswered_or_ignored_cores: List[str] = [
        entry.get("extracted_question_core", entry.get("original_question_text"))
        for entry in current_log
        if entry.get("status") in ["unanswered_pending", "unanswered_ignored"]
    ]
    previous_questions_text_for_llm = (
        "\n".join([f"- {q}" for q in previous_unanswered_or_ignored_cores])
        if previous_unanswered_or_ignored_cores
        else "Nenhuma"
    )

    # --- Prompt para Extrair Múltiplas Perguntas e Checar Similaridade ---
    multi_extract_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um especialista em análise semântica de conversas. Sua tarefa é:
1. Ler a 'Mensagem Atual do Cliente'.
2. Identificar **TODAS** as perguntas distintas feitas pelo cliente nesta mensagem.
3. Para **CADA** pergunta identificada:
    a. Extrair o núcleo da pergunta, removendo introduções/agradecimentos. Chame de `extracted_question`.
    b. Comparar essa `extracted_question` com a lista de 'Perguntas Anteriores Não Respondidas'.
    c. Determinar se ela é semanticamente similar a alguma anterior (`is_similar`: true/false).
    d. Se for similar, identificar a pergunta anterior mais parecida em `most_similar_previous_question`.

**Perguntas Anteriores Não Respondidas:**
{previous_questions}

**Mensagem Atual do Cliente:**
{current_message}

Responda APENAS com um objeto JSON seguindo o schema MultiQuestionAnalysisOutput, contendo uma lista `analyzed_questions`, onde cada item segue o schema ExtractedQuestionInfo (`extracted_question`, `is_similar`, `most_similar_previous_question`). Se nenhuma pergunta for encontrada na mensagem atual, retorne uma lista vazia.""",
            ),
        ]
    )
    structured_llm_multi = llm_fast.with_structured_output(MultiQuestionAnalysisOutput)
    chain_multi = multi_extract_prompt | structured_llm_multi

    try:
        analysis_result: MultiQuestionAnalysisOutput = await chain_multi.ainvoke(
            {
                "previous_questions": previous_questions_text_for_llm,
                "current_message": current_message_original_text,
            }
        )
        extracted_questions_info = analysis_result.analyzed_questions
        logger.info(
            f"[{node_name}] Extracted {len(extracted_questions_info)} questions from current message."
        )
        logger.debug(f"[{node_name}] Analysis details: {extracted_questions_info}")

    except Exception as e:
        logger.exception(
            f"[{node_name}] Error during multi-question extraction/similarity check: {e}"
        )
        # Se a extração falhar, não teremos perguntas atuais para processar
        return {
            "customer_question_log": current_log,
            "current_questions": None,
            "error": f"Question extraction failed: {e}",
        }

    # --- Processar Cada Pergunta Extraída e Atualizar Log ---
    current_questions_list_for_state: List[CustomerQuestionEntry] = []

    if not extracted_questions_info:
        logger.debug(f"[{node_name}] No questions extracted from the message.")
        return {"customer_question_log": current_log, "current_questions": None}

    for extracted_info in extracted_questions_info:
        extracted_core_question = extracted_info.extracted_question
        is_similar = extracted_info.is_similar
        most_similar_text = extracted_info.most_similar_previous_question

        new_entry_status: Literal[
            "asked", "repeated_unanswered", "repeated_ignored"
        ] = "asked"
        new_entry_attempts = 1
        similar_entry_index: Optional[int] = None

        if is_similar and most_similar_text:
            # Encontra a entrada original no log (match flexível)
            for i, entry in enumerate(current_log):
                if (
                    entry.get("extracted_question_core") == most_similar_text
                    or entry.get("original_question_text") == most_similar_text
                ) and entry.get("status") in [
                    "unanswered_pending",
                    "unanswered_ignored",
                ]:
                    similar_entry_index = i
                    break

        if similar_entry_index is not None:
            original_entry = current_log[similar_entry_index]
            similar_entry_status = original_entry.get("status")
            current_attempts = original_entry.get("attempts", 0)
            new_entry_attempts = current_attempts + 1

            if similar_entry_status == "unanswered_pending":
                if new_entry_attempts >= max_attempts:
                    new_entry_status = "repeated_ignored"
                    original_entry["status"] = "unanswered_ignored"
                    original_entry["attempts"] = new_entry_attempts
                    logger.warning(
                        f"[{node_name}] Question core '{extracted_core_question[:50]}...' reached max attempts. Marked original and current as ignored."
                    )
                else:
                    new_entry_status = "repeated_unanswered"
                    original_entry["attempts"] = new_entry_attempts
                    logger.info(
                        f"[{node_name}] Question core '{extracted_core_question[:50]}...' marked as 'repeated_unanswered'. Original attempts: {new_entry_attempts}"
                    )
            elif similar_entry_status == "unanswered_ignored":
                new_entry_status = "repeated_ignored"
                new_entry_attempts = original_entry.get("attempts")  # Mantém tentativas
                logger.info(
                    f"[{node_name}] Question core '{extracted_core_question[:50]}...' marked as 'repeated_ignored'."
                )
        else:
            # Se não é similar a uma não respondida/ignorada, é 'asked'
            new_entry_status = "asked"
            new_entry_attempts = 1

        # Cria a entrada para a pergunta ATUAL
        current_question_entry: CustomerQuestionEntry = {
            "original_question_text": current_message_original_text,  # Guarda o texto completo da mensagem original
            "extracted_question_core": extracted_core_question,  # Guarda o núcleo extraído
            "status": new_entry_status,
            "attempts": new_entry_attempts,
            "turn_asked": current_turn,
        }
        # Adiciona à lista de perguntas *deste turno*
        current_questions_list_for_state.append(current_question_entry)
        # Adiciona também ao log histórico persistente
        current_log.append(current_question_entry)
        logger.debug(
            f"[{node_name}] Added current question entry to log and current_questions: {current_question_entry}"
        )

    # Retorna o log histórico atualizado e a lista de perguntas do turno atual
    return {
        "customer_question_log": current_log,
        "current_questions": current_questions_list_for_state,
        "error": None,
    }


async def clarify_vague_statement_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Asks a clarifying question when the user's previous statement was vague.

    Args:
        state: Requires 'messages'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with 'generation', 'messages', and sets 'pending_agent_question'.
    """
    node_name = "clarify_vague_statement_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validações ---
    if not llm_fast:
        logger.error(f"[{node_name}] LLM unavailable. Cannot ask for clarification.")
        # O que fazer? Talvez tratar como objeção genérica? Ou só terminar? Vamos terminar.
        return {"error": "Clarification failed: LLM unavailable."}
    if not messages or not isinstance(messages[-1], HumanMessage):
        logger.error(f"[{node_name}] Last message not from user. Cannot clarify.")
        return {"error": "Clarification failed: Invalid context."}

    vague_statement = messages[-1].content
    # Tenta pegar contexto da penúltima mensagem (o que o agente disse antes)
    previous_agent_context = (
        messages[-2].content
        if len(messages) >= 2 and isinstance(messages[-2], AIMessage)
        else ""
    )

    logger.debug(
        f"[{node_name}] Clarifying vague statement: '{vague_statement[:100]}...'"
    )

    # --- Prompt para Gerar Pergunta Clarificadora ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas IA empático. O cliente acabou de fazer uma declaração vaga ou expressar uma dúvida não específica.
Sua tarefa é fazer **UMA única pergunta aberta** para entender melhor o que o cliente quis dizer ou qual é a sua preocupação/dúvida principal.

**Contexto:**
Sua Última Mensagem (Contexto): {previous_agent_message_summary}
Declaração Vaga do Cliente: {vague_statement}

**Instruções:**
1.  **Seja Específico (Se Possível):** Se a sua última mensagem ou a declaração vaga mencionam um tópico (ex: "qualificação", "implementação"), tente focar sua pergunta nesse tópico.
2.  **Seja Aberto:** Faça uma pergunta que incentive o cliente a elaborar.
3.  **Exemplos de Perguntas:** "Para que eu possa te ajudar melhor, poderia me dizer um pouco mais sobre o que está pensando?", "O que especificamente sobre [tópico, se houver] te deixou com dúvidas?", "O que te faria sentir mais claro/seguro sobre isso?", "Pode elaborar um pouco mais sobre [ponto vago]?".
4.  **Tom:** Mantenha um tom prestativo e compreensivo.
5.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}

Gere APENAS a pergunta clarificadora.""",
            ),
        ]
    )

    parser = StrOutputParser()
    chain = prompt_template | llm_fast | parser

    try:
        prev_context_summary = (
            previous_agent_context[:150] + "..."
            if len(previous_agent_context) > 150
            else previous_agent_context
        )

        clarifying_question = await chain.ainvoke(
            {
                "previous_agent_message_summary": prev_context_summary or "N/A",
                "vague_statement": vague_statement,
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )
        clarifying_question = clarifying_question.strip()

        if not clarifying_question or not clarifying_question.endswith("?"):
            raise ValueError("LLM did not generate a valid clarifying question.")

        logger.info(
            f"[{node_name}] Generated clarifying question: '{clarifying_question}'"
        )
        ai_message = AIMessage(content=clarifying_question)

        # Define esta pergunta como a nova pergunta pendente
        new_pending: PendingAgentQuestion = {
            "text": clarifying_question,
            "type": "Clarification",  # Novo tipo
            "status": "pending",
            "attempts": 1,
        }

        return {
            "generation": clarifying_question,
            "messages": [ai_message],
            "pending_agent_question": new_pending,  # Define a pergunta de clarificação como pendente
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating clarifying question: {e}")
        fallback = "Poderia me explicar um pouco melhor o que você quis dizer?"
        ai_fallback_message = AIMessage(content=fallback)
        fallback_pending: PendingAgentQuestion = {
            "text": fallback,
            "type": "Clarification_Fallback",
            "status": "pending",
            "attempts": 1,
        }
        return {
            "generation": fallback,
            "messages": [ai_fallback_message],
            "pending_agent_question": fallback_pending,
            "error": f"Clarification failed: {e}",
        }


async def generate_rapport_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a simple rapport-building response for greetings or casual input,
    incorporating basic company identity.

    Args:
        state: The current conversation state. Requires 'messages', 'company_profile'.
        config: The graph configuration. Requires 'llm_fast'.

    Returns:
        A dictionary containing the 'generation' and updated 'messages'.
    """
    node_name = "generate_rapport_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    profile_dict = state.get("company_profile")
    llm_fast_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validations ---
    if not llm_fast_instance:
        logger.error(f"[{node_name}] Fast LLM instance not found.")
        return {"error": "Rapport generation failed: LLM unavailable."}
    if not profile_dict or not isinstance(profile_dict, dict):
        logger.error(f"[{node_name}] Company profile dictionary not found in state.")
        fallback_response = AIMessage(content="Olá! Como posso ajudar?")
        return {
            "generation": fallback_response.content,
            "messages": [fallback_response],
            "error": "Missing company profile",
        }
    if not messages:
        logger.warning(f"[{node_name}] No messages found, generating default greeting.")
        company_name = profile_dict.get("company_name", "nossa empresa")
        default_greeting = AIMessage(
            content=f"Olá! Sou o assistente da {company_name}. Como posso ajudar?"
        )
        return {"generation": default_greeting.content, "messages": [default_greeting]}

    company_name = profile_dict.get("company_name", "a empresa")
    # ai_objective = profile_dict.get("ai_objective", "ajudar com suas dúvidas")
    ai_objective = "Responder à saudação/comentário inicial do cliente de forma breve, educada e convidativa."

    rapport_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""Você é um assistente virtual amigável da '{company_name}'. Seu objetivo é '{ai_objective}'.
Responda de forma breve, educada e prestativa à saudação ou comentário casual do usuário.
Mantenha o tom {profile_dict.get('sales_tone', 'profissional')}.
Use o idioma {profile_dict.get('language', 'pt-br')}.""",
            ),
            *messages[-3:],  # Considera apenas a última mensagem do usuário
        ]
    )

    parser = StrOutputParser()
    chain = rapport_prompt_template | llm_fast_instance | parser

    try:
        logger.debug(f"[{node_name}] Invoking LLM for rapport...")
        generated_text = await chain.ainvoke({})
        generated_text = generated_text.strip()

        if not generated_text:
            logger.error(f"[{node_name}] LLM returned empty response for rapport.")
            raise ValueError("LLM rapport response empty.")

        logger.info(
            f"[{node_name}] LLM generated rapport response: '{generated_text[:100]}...'"
        )
        ai_message = AIMessage(content=generated_text)
        return {"generation": generated_text, "messages": [ai_message], "error": None}

    except Exception as e:
        logger.exception(f"[{node_name}] Error invoking LLM for rapport: {e}")
        fallback_text = f"Olá! Sou da {company_name}. Em que posso ser útil hoje?"
        fallback_response = AIMessage(content=fallback_text)
        return {
            "generation": fallback_text,
            "messages": [fallback_response],
            "error": f"Rapport LLM failed: {e}",
        }


async def retrieve_knowledge_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Retrieves relevant knowledge chunks from the vector database based on the user input.
    (Previously named rag_node).
    """
    node_name = "retrieve_knowledge_node"
    logger.info(f"--- Starting Node: {node_name} ---")
    user_input = state.get("input_message")
    account_id = state.get("account_id")
    db_session_factory: Optional[Any] = config.get("configurable", {}).get(
        "db_session_factory"
    )

    # --- Dependency Checks ---
    if not user_input:
        logger.warning(f"[{node_name}] No input message. Skipping knowledge retrieval.")
        return {"retrieved_context": None}
    if not account_id:
        logger.error(f"[{node_name}] Missing account_id in state.")
        return {
            "error": "Knowledge retrieval failed: Missing account_id.",
            "retrieved_context": None,
        }
    if not db_session_factory:
        logger.error(f"[{node_name}] Missing db_session_factory in config.")
        return {
            "error": "Knowledge retrieval failed: Missing db_session_factory.",
            "retrieved_context": None,
        }
    if not EMBEDDING_AVAILABLE:
        logger.error(f"[{node_name}] Embedding function unavailable.")
        return {
            "error": "Knowledge retrieval failed: Embedding unavailable.",
            "retrieved_context": None,
        }
    if not CHUNK_REPO_AVAILABLE:
        logger.error(f"[{node_name}] Chunk repository unavailable.")
        return {
            "error": "Knowledge retrieval failed: Chunk repository unavailable.",
            "retrieved_context": None,
        }

    retrieved_context: Optional[str] = None
    try:
        logger.debug(
            f"[{node_name}] Generating embedding for input: '{user_input[:50]}...'"
        )
        query_embedding = await get_embedding(user_input)
        if query_embedding is None:
            raise ValueError("Failed to generate query embedding.")

        logger.debug(f"[{node_name}] Searching for similar chunks...")
        similar_chunks: List[KnowledgeChunk] = []
        async with db_session_factory() as db:
            similar_chunks = await search_similar_chunks(
                db=db,
                account_id=account_id,
                query_embedding=query_embedding,
                limit=RAG_CHUNK_LIMIT,
                similarity_threshold=RAG_SIMILARITY_THRESHOLD,
            )

        if similar_chunks:
            logger.info(
                f"[{node_name}] Retrieved {len(similar_chunks)} relevant chunks."
            )

            context_parts = [
                "Retrieved Knowledge Snippets (use this information to answer):"
            ]
            for i, chunk in enumerate(similar_chunks):
                source_info = (
                    chunk.metadata_.get("original_source", "Unknown source")
                    if hasattr(chunk, "metadata_") and chunk.metadata_
                    else "Unknown source"
                )
                page_info = (
                    f"(Page: {chunk.metadata_.get('page_number')})"
                    if hasattr(chunk, "metadata_")
                    and chunk.metadata_
                    and "page_number" in chunk.metadata_
                    else ""
                )
                chunk_text = getattr(chunk, "chunk_text", "N/A")
                context_parts.append(
                    f"{i+1}. [Source: {source_info} {page_info}]:\n{chunk_text}\n"
                )
            retrieved_context = "\n".join(context_parts)
            logger.debug(
                f"[{node_name}] Formatted retrieved context: {retrieved_context[:200]}..."
            )
        else:
            logger.info(f"[{node_name}] No relevant chunks found.")

    except Exception as e:
        logger.exception(f"[{node_name}] Error during knowledge retrieval: {e}")
        retrieved_context = None

    return {"retrieved_context": retrieved_context}


# --- generate_response_node  ---
async def generate_response_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates the AI's response based on the conversation history, profile,
    agent config, and potentially retrieved RAG context.
    """
    node_name = "generate_response_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    # --- Get State and Config ---
    messages = state.get("messages", [])
    current_questions: Optional[List[CustomerQuestionEntry]] = state.get(
        "current_questions"
    )

    profile = CompanyProfileSchema.model_validate(state.get("company_profile"))
    # agent_config = state.get("agent_config") # Agent config might be optional for basic response
    retrieved_context = state.get("retrieved_context")
    llm_primary_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )

    # --- Validate Inputs ---
    if not messages:
        logger.error(f"[{node_name}] Message history is empty.")
        return {"error": "Generation failed: Empty message history."}
    if not profile or not isinstance(profile, CompanyProfileSchema):
        logger.error(f"[{node_name}] Invalid or missing Company Profile.")
        return {"error": "Generation failed: Invalid company profile."}
    if not llm_primary_instance:
        logger.error(f"[{node_name}] LLM instance not found in config.")
        return {"error": "Generation failed: LLM unavailable."}
    if not PROMPT_BUILDER_AVAILABLE:
        logger.error(f"[{node_name}] Prompt builder unavailable.")
        return {"error": "Generation failed: Prompt builder unavailable."}

    if not current_questions:
        logger.debug(
            f"[{node_name}] No current questions identified by previous node. Skipping specific response generation (prompt builder might handle)."
        )

    # --- Build Prompt ---
    try:
        brasilia_tz = pytz.timezone("America/Sao_Paulo")
        current_time_str = datetime.now(brasilia_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        # Pass current stage if available, prompt builder might use it
        current_stage = state.get("current_sales_stage")
        logger.debug(
            f"[{node_name}] Building prompt for stage: {current_stage}, with RAG context: {bool(retrieved_context)}"
        )
        prompt_messages = build_llm_prompt_messages(
            profile=profile,
            chat_history_lc=messages,
            current_datetime=current_time_str,
            retrieved_context=retrieved_context,
            current_questions=current_questions,
            # Optional: Pass stage to prompt builder if it uses it
            # current_stage=current_stage
        )
        if not prompt_messages:
            raise ValueError("Prompt builder returned empty messages.")
        logger.trace(f"[{node_name}] System Prompt: {prompt_messages[0].content}")
        logger.trace(f"[{node_name}] History/Input Messages: {prompt_messages[1:]}")

    except Exception as e:
        logger.exception(f"[{node_name}] Error building prompt messages: {e}")
        return {"error": f"Prompt building failed: {e}"}

    # --- Invoke LLM ---
    try:
        logger.debug(f"[{node_name}] Invoking LLM...")
        ai_response: BaseMessage = await llm_primary_instance.ainvoke(prompt_messages)

        if not isinstance(ai_response, AIMessage) or not ai_response.content:
            logger.error(
                f"[{node_name}] LLM returned invalid response type or empty content: {ai_response}"
            )
            raise ValueError("LLM response invalid or empty.")

        generated_text = ai_response.content.strip()
        logger.info(
            f"[{node_name}] LLM generated response: '{generated_text[:100]}...'"
        )

        # Return the generation and the AI message to be added to the state
        return {
            "generation": generated_text,
            "messages": [ai_response],
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error invoking LLM: {e}")
        # Fallback response or error state
        fallback_text = "Desculpe, não consegui processar sua solicitação no momento."
        fallback_response = AIMessage(content=fallback_text)
        return {
            "generation": fallback_text,
            "messages": [fallback_response],
            "error": f"LLM invocation failed: {e}",
        }


async def define_proposal_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Analyzes the conversation and company offerings to define the specific
    solution details (product, price, quantity) being proposed before closing.

    Args:
        state: Requires 'messages', 'company_profile', 'customer_needs', 'customer_pain_points'.
        config: Requires 'llm_primary_instance'.

    Returns:
        Dictionary containing 'proposed_solution_details'.
    """
    node_name = "define_proposal_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    profile = CompanyProfileSchema.model_validate(
        state.get("company_profile")
    )  # Validar para acesso
    needs = state.get("customer_needs", [])
    pains = state.get("customer_pain_points", [])
    llm_primary: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )

    # --- Validações ---
    if not llm_primary:
        return {"error": "Proposal definition failed: LLM unavailable."}
    if not profile:
        return {"error": "Proposal definition failed: Missing profile."}
    if not messages:
        return {"error": "Proposal definition failed: Empty message history."}
    if not needs and not pains:
        logger.warning(
            f"[{node_name}] No specific needs or pains identified, proposal might be generic."
        )

    # --- Preparar Contexto para o LLM ---
    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(messages[-8:])
        ]
    )
    needs_summary = "; ".join(needs) if needs else "N/A"
    pains_summary = "; ".join(pains) if pains else "N/A"
    # Formatar ofertas para o prompt
    offerings_text = (
        "\n".join(
            [
                f"- {o.name}: {o.short_description} (Preço: {o.price_info or 'N/A'})"
                for o in profile.offering_overview
            ]
        )
        if profile.offering_overview
        else "Nenhuma oferta específica listada."
    )

    logger.debug(
        f"[{node_name}] Defining proposal based on Needs: '{needs_summary}', Pains: '{pains_summary}'"
    )

    # --- Prompt para Definir a Proposta ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um especialista em vendas que precisa definir a proposta final para o cliente com base na conversa.
Analise as necessidades/dores do cliente e as ofertas da empresa para determinar a melhor solução a ser proposta.

**Contexto:**
Necessidades do Cliente: {customer_needs}
Dores/Problemas do Cliente: {customer_pains}
Ofertas da Empresa:
{company_offerings}

Histórico Recente da Conversa:
{chat_history}

**Sua Tarefa:**
1.  **Identifique o Produto Principal:** Qual produto/serviço da lista de 'Ofertas da Empresa' melhor atende às necessidades/dores identificadas?
2.  **Determine Detalhes:**
    *   `product_name`: Nome exato do produto/serviço principal identificado.
    *   `quantity`: Quantidade (geralmente 1, a menos que a conversa indique outra).
    *   `price`: Preço total para a quantidade (se disponível nas ofertas ou inferível). Deixe null se não souber.
    *   `price_info`: Informação adicional do preço (ex: "por mês", "taxa única").
    *   `key_benefit_addressed`: A principal necessidade/dor que esta proposta resolve.
    *   `delivery_info`: Informação relevante de entrega/setup, se houver.
3.  **Output:** Responda APENAS com um objeto JSON seguindo o schema ProposedSolutionDetails.

Instrução Final: Defina a proposta mais adequada em formato JSON.""",
            ),
        ]
    )

    # --- Cadeia com LLM Estruturado ---
    # Usar um LLM capaz de extrair JSON (o primário deve ser)
    structured_llm = llm_primary.with_structured_output(ProposedSolutionDetails)
    chain = prompt_template | structured_llm

    try:
        proposal_details: ProposedSolutionDetails = await chain.ainvoke(
            {
                "customer_needs": needs_summary,
                "customer_pains": pains_summary,
                "company_offerings": offerings_text,
                "chat_history": formatted_history,
            }
        )

        logger.info(f"[{node_name}] Defined proposal details: {proposal_details}")

        # Retorna o dicionário para ser adicionado ao estado
        return {
            "proposed_solution_details": proposal_details.model_dump(
                exclude_none=True
            ),  # Converte para dict
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error defining proposal details: {e}")
        # Retorna vazio ou um erro, impedindo o fechamento sem detalhes
        return {
            "proposed_solution_details": None,
            "error": f"Proposal definition failed: {e}",
        }


async def present_capability_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a response presenting the product/service capability that addresses
    the explicitly identified customer need. Focuses on Benefits.

    Args:
        state: Requires 'messages', 'company_profile', 'customer_needs', 'retrieved_context'.
        config: Requires 'llm_instance'.

    Returns:
        Dictionary with 'generation' and updated 'messages'.
    """
    node_name = "present_capability_node"
    logger.info(f"--- Starting Node: {node_name} ---")
    logger.debug(f"Recieved state: {state}")

    messages = state.get("messages", [])
    profile = CompanyProfileSchema.model_validate(state.get("company_profile"))
    needs = state.get("customer_needs", [])
    context = state.get("retrieved_context")
    llm_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )

    # --- Validações ---
    if not llm_instance:
        return {"error": "Presentation failed: LLM unavailable."}
    if not profile:
        return {"error": "Presentation failed: Missing profile."}
    if not needs:
        return {"error": "Presentation failed: No explicit needs identified."}

    primary_need = needs[-1] if needs else "atender às suas necessidades"
    logger.debug(f"[{node_name}] Presenting capability based on need: '{primary_need}'")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas focado em apresentar soluções que resolvem necessidades explícitas do cliente.
O cliente expressou a seguinte necessidade: **"{explicit_need}"**.
Sua tarefa é apresentar como o produto/serviço da **{company_name}** atende a essa necessidade, focando nos **BENEFÍCIOS** para o cliente.
Use o CONTEXTO ADICIONAL (se disponível) sobre o produto/serviço. Mantenha o tom {sales_tone}.
Seja claro e conecte diretamente a solução à necessidade do cliente. Termine com uma pergunta aberta ou um próximo passo suave (avanço).

{formatting_instructions}

PERFIL DA EMPRESA: {company_name}, {business_description}
Ofertas Relevantes (Contexto): {offering_summary}

CONTEXTO ADICIONAL (RAG):
{additional_context}

HISTÓRICO RECENTE:
{chat_history}

Instrução: Apresente a capacidade da solução focando no benefício para a necessidade '{explicit_need}'.""",
            ),
        ]
    )

    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(messages[-4:])
        ]
    )
    parser = StrOutputParser()
    chain = prompt_template | llm_instance | parser

    try:
        generated_presentation = await chain.ainvoke(
            {
                "explicit_need": primary_need,
                "company_name": profile.company_name,
                "business_description": profile.business_description,
                "sales_tone": profile.sales_tone,
                "offering_summary": (
                    ", ".join([o.name for o in profile.offering_overview[:3]])
                    if profile.offering_overview
                    else "N/A"
                ),
                "additional_context": (
                    context
                    if context
                    else "Nenhuma informação adicional específica recuperada."
                ),
                "chat_history": formatted_history if formatted_history else "N/A",
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )
        generated_presentation = generated_presentation.strip()

        if not generated_presentation:
            raise ValueError("LLM returned empty presentation.")

        logger.info(
            f"[{node_name}] Generated capability presentation: '{generated_presentation[:100]}...'"
        )
        ai_message = AIMessage(content=generated_presentation)

        return {
            "generation": generated_presentation,
            "messages": [ai_message],
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating capability presentation: {e}")
        fallback = "Entendido. Com base no que você disse, nosso produto pode ajudar. Gostaria de saber mais?"
        ai_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_message],
            "error": f"Presentation generation failed: {e}",
        }


async def end_conversation_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a final, polite closing message for the conversation.

    Args:
        state: Current conversation state. May use 'disengagement_reason' for context.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with 'generation' and 'messages'. This node leads to END.
    """
    node_name = "end_conversation_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    reason = state.get("disengagement_reason")  # Opcional: motivo do fim
    profile_dict = state.get("company_profile")
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validações ---
    if not llm_fast:
        logger.error(f"[{node_name}] LLM unavailable. Using generic fallback.")
        fallback = "Agradeço seu contato. Tenha um ótimo dia!"
        return {"generation": fallback, "messages": [AIMessage(content=fallback)]}
    if not profile_dict:
        logger.warning(f"[{node_name}] Profile not found. Using generic fallback.")
        fallback = "Agradeço seu contato. Tenha um ótimo dia!"
        return {"generation": fallback, "messages": [AIMessage(content=fallback)]}

    logger.debug(f"[{node_name}] Ending conversation. Reason (if any): {reason}")

    # --- Prompt para Mensagem Final ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas IA educado encerrando a conversa.
O motivo do encerramento foi: {reason_context}.

**Sua Tarefa:**
1.  **Agradeça:** Agradeça ao cliente pelo tempo ou interesse.
2.  **Reconheça (Opcional):** Se houver um motivo claro (ex: cliente disse não, limite atingido), reconheça brevemente de forma neutra (ex: "Entendido.").
3.  **Despeça-se:** Deseje um bom dia/tarde/noite.
4.  **Ofereça Ajuda Futura (Opcional Suave):** Se apropriado (especialmente se o motivo não foi rejeição forte), mencione que está à disposição caso ele mude de ideia ou precise de algo no futuro. Use com moderação.
5.  **Tom:** Mantenha o tom {sales_tone}, mas adaptado para ser cordial e finalizador.
6.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}

Gere APENAS a mensagem final de despedida.""",
            ),
        ]
    )

    parser = StrOutputParser()
    chain = prompt_template | llm_fast | parser

    try:
        reason_context = (
            reason if reason else "Fim da interação solicitada ou fluxo concluído."
        )

        final_message = await chain.ainvoke(
            {
                "reason_context": reason_context,
                "sales_tone": profile_dict.get("sales_tone", "profissional"),
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )
        final_message = final_message.strip()

        if not final_message:
            raise ValueError("LLM returned empty final message.")

        logger.info(f"[{node_name}] Generated final message: '{final_message}'")
        ai_message = AIMessage(content=final_message)

        # Limpa estado pendente ao finalizar? Opcional.
        # state['pending_agent_question'] = None

        return {
            "generation": final_message,
            "messages": [ai_message],
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating final message: {e}")
        fallback = "Agradeço seu tempo e interesse. Tenha um ótimo dia!"
        ai_fallback_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_fallback_message],
            "error": f"End conversation failed: {e}",
        }


async def transition_after_answer_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a transition after answering a direct user question, attempting
    to smoothly return to the agent's previous line of questioning if one
    was pending. Otherwise, asks a new relevant question.

    Args:
        state: Requires 'messages', 'generation', 'pending_agent_question'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with updated 'generation' (original answer + transition),
        'messages' (only the transition part as AIMessage), and updated
        'pending_agent_question'.
    """
    node_name = "transition_after_answer_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    # Resposta completa dada pelo generate_response_node à pergunta do usuário
    agent_answer_to_user_question = state.get("generation", "")
    # Verifica se há pergunta pendente do agente
    pending_question = state.get("pending_agent_question")

    llm_fast_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validações ---
    if not llm_fast_instance:
        logger.error(f"[{node_name}] LLM unavailable. Skipping transition.")
        return {
            "generation": agent_answer_to_user_question,
            "messages": [],
            "pending_agent_question": pending_question,
        }  # Retorna estado atual
    if not agent_answer_to_user_question:
        logger.warning(
            f"[{node_name}] No previous generation found. Skipping transition."
        )
        return {
            "generation": agent_answer_to_user_question,
            "messages": [],
            "pending_agent_question": pending_question,
        }
    if not messages or len(messages) < 2:
        logger.warning(
            f"[{node_name}] Not enough message history. Skipping transition."
        )
        return {
            "generation": agent_answer_to_user_question,
            "messages": [],
            "pending_agent_question": pending_question,
        }

    # Determina se há uma pergunta a ser retomada
    output_transition_text: Optional[str] = None
    output_pending_question: Optional[PendingAgentQuestion] = None
    output_error: Optional[str] = None

    question_to_resume_text: Optional[str] = None
    if (
        pending_question
        and isinstance(pending_question, dict)
        and pending_question.get("status") == "pending"
    ):
        question_to_resume_text = pending_question.get("text")
        logger.info(
            f"[{node_name}] Pending question found to resume: '{question_to_resume_text}'"
        )
    else:
        logger.info(
            f"[{node_name}] No pending question to resume. Will generate a new question."
        )

    # --- Prompt para Gerar a Transição (Retomando ou Nova) ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas IA. Você acabou de fornecer a seguinte resposta ({agent_answer_summary}) à pergunta/declaração do cliente.
Sua tarefa é criar uma transição suave para continuar a conversa, adaptando-se à qualidade da sua resposta anterior.

**Instruções IMPORTANTES:**
1.  **Analise a Sua Resposta Anterior ({agent_answer_summary}):**
    *   **Se a sua resposta indica que você NÃO PÔDE responder à pergunta principal do cliente** (ex: contém frases como "não tenho essa informação", "não sei dizer", "recomendo entrar em contato", "não consigo ajudar com isso especificamente", "no momento não tenho detalhes sobre"):
        *   **NÃO** tente retomar uma pergunta anterior complexa ({previous_agent_question}).
        *   **NÃO** inicie uma nova linha de investigação profunda (SPIN).
        *   Gere uma transição **simples e aberta**, focando no que você *pode* fazer ou devolvendo o controle. Exemplos: "Posso te ajudar com mais alguma dúvida sobre as funcionalidades que mencionei?", "Há algo mais sobre o *Vendedor IA* em que posso te ajudar agora?", "Em que mais posso ser útil no momento?". Defina `question_type` como 'Open_Fallback'.
    *   **Se a sua resposta respondeu satisfatoriamente à pergunta do cliente:** Siga as instruções normais abaixo.

**Instruções Normais (Se você respondeu à pergunta):**
2.  **Confirme Utilidade (Opcional):** Comece com "Espero que isso tenha ajudado a esclarecer." ou "Fez sentido?".
3.  **Decida a Próxima Pergunta:**
    *   **Se uma 'Pergunta Anterior a Retomar' ({previous_agent_question}) foi fornecida E ela ainda faz sentido no contexto:** Reintroduza essa pergunta de forma natural. Defina `question_type` como 'Resume_Pending'.
    *   **Caso contrário (sem pergunta anterior ou ela não faz mais sentido):** Gere uma *nova pergunta aberta* relevante para continuar a investigação (Problema/Implicação). Defina `question_type` como 'New_Investigation'.
4.  **Seja Conciso e Natural.**
5.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}
6.  **Output:** Responda APENAS com um objeto JSON seguindo o schema TransitionOutput (`transition_text`, `question_asked`, `question_type`).""",
            ),
            ("user", "Gere a transição apropriada."),
        ]
    )

    # --- Cadeia com LLM Estruturado ---
    structured_llm = llm_fast_instance.with_structured_output(TransitionOutput)
    chain = prompt_template | structured_llm

    try:
        answer_summary = (
            agent_answer_to_user_question[:150] + "..."
            if len(agent_answer_to_user_question) > 150
            else agent_answer_to_user_question
        )

        transition_result: TransitionOutput = await chain.ainvoke(
            {
                "agent_answer_summary": answer_summary,
                "previous_agent_question": question_to_resume_text
                or "N/A",  # Passa a pergunta a retomar ou N/A
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )

        logger.info(f"[{node_name}] Structured transition result: {transition_result}")

        transition_text = transition_result.transition_text.strip()
        question_asked_text = transition_result.question_asked.strip()
        question_asked_type = (
            transition_result.question_type
        )  # 'Resume_Pending' ou 'New_Investigation'

        if (
            not transition_text
            or not question_asked_text
            or not question_asked_text.endswith("?")
        ):
            raise ValueError("Invalid transition data")

        output_transition_text = transition_text

        # --- Define o estado de pending_question para o retorno ---
        if question_asked_type == "Resume_Pending" and pending_question:
            # Se retomou, retorna o objeto PENDENTE EXISTENTE (com attempts já incrementado)
            output_pending_question = pending_question
            logger.debug(
                f"[{node_name}] Resuming pending question. Returning existing state: {output_pending_question}"
            )
        else:  # Gerou nova pergunta
            # Cria um NOVO objeto pending_question com attempts = 1
            output_pending_question = {
                "text": question_asked_text,
                "type": question_asked_type,
                "status": "pending",
                "attempts": 1,
            }
            logger.debug(
                f"[{node_name}] Generated new question. Setting new pending state: {output_pending_question}"
            )

        output_error = None

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating transition: {e}")
        output_error = f"Transition generation failed: {e}"
        # Mantém o estado pendente original em caso de erro na geração da transição? Sim.
        output_pending_question = pending_question

    # --- Prepara o Estado de Retorno Final ---
    final_response_text = agent_answer_to_user_question  # Resposta original
    output_messages = []  # Mensagens a adicionar ao histórico do grafo

    if output_transition_text:
        final_response_text = (
            f"{agent_answer_to_user_question}\n\n{output_transition_text}"
        )
        ai_transition_message = AIMessage(content=output_transition_text)
        output_messages = [ai_transition_message]
        logger.info(f"[{node_name}] Generated transition: '{output_transition_text}'")
    else:
        logger.warning(f"[{node_name}] No transition text generated.")

    return {
        "generation": final_response_text,  # Resposta completa (original + transição se houver)
        "messages": output_messages,  # Apenas a transição (se houver)
        "pending_agent_question": output_pending_question,  # <-- Retorna o objeto correto (novo ou existente)
        "error": output_error,
    }


async def handle_impasse_node(state: ConversationState, config: dict) -> Dict[str, Any]:
    """
    Generates a message acknowledging the impasse due to a repeated unanswered
    question and offers clear final options.

    Args:
        state: Requires 'messages', 'customer_question_log', 'company_profile'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with 'generation' and 'messages'. This node leads to END.
    """
    node_name = "handle_impasse_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    customer_log: List[CustomerQuestionEntry] = state.get("customer_question_log", [])
    profile_dict = state.get("company_profile")
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validações ---
    if not llm_fast:
        logger.error(f"[{node_name}] LLM unavailable. Using generic impasse fallback.")
        fallback = "Percebo que não consegui responder completamente sua dúvida anterior. Podemos tentar outro assunto ou encerrar por agora?"
        return {"generation": fallback, "messages": [AIMessage(content=fallback)]}
    if not profile_dict:
        logger.warning(f"[{node_name}] Profile not found. Using generic fallback.")
        fallback = "Percebo que não consegui responder completamente sua dúvida anterior. Podemos tentar outro assunto ou encerrar por agora?"
        return {"generation": fallback, "messages": [AIMessage(content=fallback)]}
    if not customer_log:
        logger.error(
            f"[{node_name}] Customer log is empty. Cannot determine impasse context."
        )
        fallback = "Parece que chegamos a um ponto onde não consigo ajudar mais especificamente. Gostaria de tentar outro assunto?"
        return {"generation": fallback, "messages": [AIMessage(content=fallback)]}

    # Encontra a última pergunta marcada como ignorada para dar contexto
    ignored_question_text = "uma questão anterior"
    last_entry = customer_log[-1]
    if last_entry.get("status") == "repeated_ignored":
        # Tenta encontrar o texto original buscando para trás por uma entrada similar
        # com status 'unanswered_ignored' (marcada pelo update_log)
        original_text = last_entry.get(
            "question_text"
        )  # Usa o texto da última como fallback
        for entry in reversed(customer_log[:-1]):
            # Simplificação: assume que a última entrada ignorada no log é a relevante
            if entry.get("status") == "unanswered_ignored":
                original_text = entry.get("question_text", original_text)
                break
        ignored_question_text = original_text

    logger.warning(
        f"[{node_name}] Handling impasse regarding question: '{ignored_question_text[:100]}...'"
    )

    # --- Prompt Específico para Impasse ---
    impasse_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas IA educado e direto. A conversa chegou a um impasse porque o cliente repetiu várias vezes uma pergunta ('{ignored_question}') que você indicou não poder responder. Sua estratégia de redirecionamento falhou.

**Sua Tarefa AGORA:**
1.  **Reconheça o Impasse:** Admita de forma clara e educada que você não pode fornecer a informação específica solicitada, apesar das tentativas. (Ex: "Percebo que a informação sobre '{ignored_question}' é realmente crucial para você e, como já mencionei, infelizmente não a tenho disponível neste momento para seguirmos *nesta* linha específica.").
2.  **Ofereça uma Escolha Final Clara e Fechada:** Apresente 2 ou 3 opções concretas e limitadas para o cliente decidir o rumo. As opções devem ser ações que você *pode* realizar ou o encerramento.
    *   **Exemplo de Opções:** "[Opção 1: Agendar uma demonstração], [Opção 2: Discutir o benefício X em detalhes] ou, se preferir, podemos encerrar nossa conversa por agora." (Adapte as opções ao contexto, se possível, mas mantenha-as concretas).
    *   **Estrutura da Pergunta Final:** "Qual dessas opções faz mais sentido para você neste momento?" ou "Como você gostaria de prosseguir?".
3.  **Tom:** Mantenha o tom {sales_tone}, mas firme e resolutivo, focado em obter uma decisão do cliente sobre os próximos passos possíveis.
4.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}

Gere APENAS a mensagem que reconhece o impasse e apresenta as opções finais.""",
            ),
        ]
    )

    parser = StrOutputParser()
    chain = impasse_prompt_template | llm_fast | parser

    try:
        impasse_message = await chain.ainvoke(
            {
                "ignored_question": ignored_question_text,
                "sales_tone": profile_dict.get("sales_tone", "profissional"),
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
                # Poderia passar mais contexto aqui se necessário (ex: últimas alternativas oferecidas)
            }
        )
        impasse_message = impasse_message.strip()

        if not impasse_message:
            raise ValueError("LLM returned empty impasse message.")

        logger.info(f"[{node_name}] Generated impasse message: '{impasse_message}'")
        ai_message = AIMessage(content=impasse_message)

        # Define um motivo de desengajamento opcional
        state["disengagement_reason"] = (
            f"Impasse reached on question: {ignored_question_text}"
        )

        return {
            "generation": impasse_message,
            "messages": [ai_message],
            "error": None,
            # Não precisa mexer no pending_agent_question aqui, pois estamos encerrando ou esperando a escolha final
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating impasse message: {e}")
        fallback = "Percebo que não consegui ajudar com sua última questão como esperado. Podemos tentar focar em outro aspecto ou prefere encerrar por agora?"
        ai_fallback_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_fallback_message],
            "error": f"Impasse handling failed: {e}",
        }
