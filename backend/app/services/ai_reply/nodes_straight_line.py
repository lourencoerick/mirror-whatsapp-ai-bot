# backend/app/services/ai_reply/nodes_straight_line.py

from typing import Dict, Any, List, Optional, Literal
from loguru import logger


# Import State and Constants
from .graph_state import (
    ConversationState,
    CompanyProfileSchema,
    BotAgentRead,
    CERTAINTY_STATUS_STATEMENT_MADE,
)

# Import LLM and related components
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import (
        BaseMessage,
        AIMessage,
        HumanMessage,
        SystemMessage,
    )
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    logger.error("LangChain core not found for Straight Line nodes.")

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

    class ChatPromptTemplate:
        @classmethod
        def from_messages(cls, *args, **kwargs):
            return cls()

        async def ainvoke(self, *args, **kwargs):
            return []


try:
    from app.core.embedding_utils import get_embedding

    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.error("Embedding utils not found for Straight Line RAG.")

    async def get_embedding(*args, **kwargs):
        return None


try:
    from app.services.repository.knowledge_chunk import search_similar_chunks
    from app.models.knowledge_chunk import KnowledgeChunk

    CHUNK_REPO_AVAILABLE = True
except ImportError:
    CHUNK_REPO_AVAILABLE = False
    logger.error("Knowledge repository not found for Straight Line RAG.")

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

from app.services.ai_reply.prompt_utils import WHATSAPP_MARKDOWN_INSTRUCTIONS
from trustcall import create_extractor

# --- Pydantic Schema for Certainty Assessment Output ---
from pydantic import BaseModel, Field, conint


class CertaintyAssessmentOutput(BaseModel):
    """Structured output for customer certainty assessment."""

    product: conint(ge=0, le=10) = Field(
        ...,
        description="Customer's certainty level (0-10) about the product/solution itself.",
    )
    agent: conint(ge=0, le=10) = Field(
        ...,
        description="Customer's certainty level (0-10) about the agent/salesperson.",
    )
    company: conint(ge=0, le=10) = Field(
        ...,
        description="Customer's certainty level (0-10) about the company's reputation/reliability.",
    )


class CertaintyGenerationOutput(BaseModel):
    """Structured output for generating certainty statements."""

    connection_phrase: Optional[str] = Field(
        None,
        description="An optional short phrase connecting to the customer's last message, showing understanding. Null or empty if no specific connection is needed.",
    )
    certainty_statement: str = Field(
        ...,
        description="The specific, confident statement focused on building certainty about the product, agent, or company (based on the focus). Should NOT end with a question.",
    )


# Constants
CERTAINTY_THRESHOLD = 7  # Target certainty level (0-10)
RAG_CHUNK_LIMIT = 3  # Limit for certainty RAG
RAG_SIMILARITY_THRESHOLD = 0.5  # Threshold for certainty RAG

# ==============================================================================
# Straight Line Subgraph Nodes
# ==============================================================================


async def assess_certainty_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Uses an LLM with structured output (trustcall or with_structured_output)
    to assess the customer's perceived certainty level in the product, agent, and company.

    Args:
        state: Current state, requires 'messages'.
        config: Requires 'llm_fast'.

    Returns:
        Dictionary with updated 'certainty_level'. Defaults on error.
    """
    node_name = "assess_certainty_node"
    logger.info(f"--- Starting Node: {node_name} (Straight Line Subgraph) ---")

    messages = state.get("messages", [])
    llm_fast_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )  # Use fast LLM
    extractor = create_extractor(
        llm_fast_instance,
        tools=[CertaintyAssessmentOutput],
        tool_choice=CertaintyAssessmentOutput.__name__,
    )
    current_certainty = state.get(
        "certainty_level", {"product": 5, "agent": 5, "company": 5}
    )  # Default neutral

    # --- Validations ---
    if not llm_fast_instance:
        logger.error(f"[{node_name}] Fast LLM instance not found.")
        return {
            "error": "Certainty assessment failed: LLM unavailable.",
            "certainty_level": current_certainty,
        }
    if not messages or len(messages) < 2:
        logger.warning(
            f"[{node_name}] Not enough message history for certainty assessment."
        )
        return {"certainty_level": current_certainty}  # Return current/default

    history_to_analyze = messages[-6:]
    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(history_to_analyze)
        ]
    )
    logger.debug(
        f"[{node_name}] Assessing certainty based on history:\n{formatted_history}"
    )

    # --- Prompt for Assessment ---
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um analista de vendas expert em detectar o nível de certeza do cliente. Analise o histórico recente da conversa.
Com base nas perguntas, declarações e tom do **Cliente**, avalie o nível de certeza dele (de 0 a 10, onde 10 é certeza absoluta) em relação a três áreas:
1.  **Produto/Serviço:** Quão convencido ele parece sobre a solução em si?
2.  **Agente (Você):** Quão confiante ele parece em você como vendedor/especialista?
3.  **Empresa:** Quão seguro ele parece sobre a reputação/confiabilidade da sua empresa?

HISTÓRICO RECENTE:
{chat_history}

Avalie os três níveis de certeza.""",
            ),
        ]
    )
    try:

        # --- Use Structured Output ---
        result = await extractor.ainvoke(
            prompt.format_prompt(chat_history=formatted_history)
        )

        logger.debug(f"[{node_name}] Raw result from trustcall: {result}")

        responses = result.get("responses")
        if isinstance(responses, list) and len(responses) > 0:
            assessment = responses[0]
            if isinstance(assessment, CertaintyAssessmentOutput):
                logger.info(
                    f"[{node_name}] Trustcall extraction successful: {assessment}"
                )

                return {
                    "certainty_level": {
                        "product": assessment.product,
                        "agent": assessment.agent,
                        "company": assessment.company,
                    },
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
        # Fallback seguro
        return {
            # **default_return,  # Retorna valores padrão
            "error": f"Analysis failed: {e}",
        }


async def select_certainty_focus_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Selects which 'Three Ten' (product, agent, company) needs reinforcement.

    Args:
        state: Current state, requires 'certainty_level'.
        config: Graph config.

    Returns:
        Dictionary with 'certainty_focus' set to 'product', 'agent', 'company', or None.
    """
    node_name = "select_certainty_focus_node"
    logger.info(f"--- Starting Node: {node_name} (Straight Line Subgraph) ---")

    certainty_level = state.get("certainty_level")
    focus = None

    if not certainty_level or not isinstance(certainty_level, dict):
        logger.warning(
            f"[{node_name}] Invalid or missing certainty_level in state. Cannot select focus."
        )
        return {"certainty_focus": None}

    # Find the area with the lowest score that is below the threshold
    lowest_score = CERTAINTY_THRESHOLD
    candidates = []
    for key, score in certainty_level.items():
        if (
            key in ["product", "agent", "company"]
            and isinstance(score, int)
            and score < CERTAINTY_THRESHOLD
        ):
            candidates.append((key, score))

    if candidates:
        # Sort by score (lowest first) to focus on the weakest area
        candidates.sort(key=lambda item: item[1])
        focus = candidates[0][0]
        lowest_score = candidates[0][1]
        logger.info(
            f"[{node_name}] Selected focus for building certainty: {focus} (Score: {lowest_score})"
        )
    else:
        logger.info(
            f"[{node_name}] All certainty levels meet or exceed threshold ({CERTAINTY_THRESHOLD})."
        )

    return {"certainty_focus": focus}


async def retrieve_knowledge_for_certainty_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Retrieves knowledge specifically relevant to the 'certainty_focus'.

    Args:
        state: Requires 'certainty_focus', 'input_message', 'account_id'.
        config: Requires 'db_session_factory'.

    Returns:
        Dictionary with 'retrieved_context' specific to the focus.
    """
    node_name = "retrieve_knowledge_for_certainty_node"
    logger.info(f"--- Starting Node: {node_name} (Straight Line Subgraph) ---")

    focus = state.get("certainty_focus")

    # For now, using last message + focus.
    input_message = state.get("input_message", "")
    account_id = state.get("account_id")
    db_session_factory: Optional[async_sessionmaker[AsyncSession]] = config.get(
        "configurable", {}
    ).get("db_session_factory")

    if not focus:
        logger.debug(f"[{node_name}] No certainty focus. Skipping knowledge retrieval.")
        return {"retrieved_context": None}
    if (
        not account_id
        or not db_session_factory
        or not EMBEDDING_AVAILABLE
        or not CHUNK_REPO_AVAILABLE
    ):
        logger.error(f"[{node_name}] Missing dependencies for RAG. Skipping.")
        return {"retrieved_context": None}

    # --- Modify Query based on Focus ---
    if focus == "agent":
        query_text = f"Depoimentos de clientes ou informações que comprovem a expertise do vendedor sobre: {input_message}"
    elif focus == "company":
        query_text = f"Informações sobre a reputação, confiabilidade ou história da empresa relacionadas a: {input_message}"
    elif focus == "product":
        query_text = f"Detalhes, benefícios ou provas sobre o produto/serviço relacionados a: {input_message}"
    else:  # Should not happen if focus is validated
        query_text = input_message

    logger.debug(
        f"[{node_name}] RAG query for focus '{focus}': '{query_text[:100]}...'"
    )

    # --- Call RAG ---
    retrieved_context: Optional[str] = None
    try:
        query_embedding = await get_embedding(query_text)
        if query_embedding is None:
            raise ValueError("Failed embedding.")

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
                f"[{node_name}] Retrieved {len(similar_chunks)} chunks for focus '{focus}'."
            )
            context_parts = [f"Informações Relevantes ({focus}):"]
            for i, chunk in enumerate(similar_chunks):
                source_info = (
                    chunk.metadata_.get("original_source", "?")
                    if hasattr(chunk, "metadata_") and chunk.metadata_
                    else "?"
                )
                chunk_text = getattr(chunk, "chunk_text", "N/A")
                context_parts.append(f"{i+1}. [{source_info}]: {chunk_text}\n")
            retrieved_context = "\n".join(context_parts)
            logger.trace(f"[{node_name}] Formatted context: {retrieved_context}")
        else:
            logger.info(f"[{node_name}] No specific chunks found for focus '{focus}'.")

    except Exception as e:
        logger.exception(f"[{node_name}] Error during focused RAG: {e}")
        retrieved_context = None

    return {"retrieved_context": retrieved_context}


async def generate_certainty_statement_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a persuasive statement to build certainty using structured output,
    ensuring the connection phrase accurately reflects the customer's sentiment.

    Args:
        state: Requires 'messages', 'company_profile', 'certainty_focus', 'retrieved_context'.
        config: Requires 'llm_primary_instance'.

    Returns:
        Dictionary with 'generation', 'messages', and updated 'certainty_status'.
    """
    node_name = "generate_certainty_statement_node"
    logger.info(f"--- Starting Node: {node_name} (Straight Line Subgraph) ---")

    messages = state.get("messages", [])
    profile_dict = state.get("company_profile")
    focus = state.get("certainty_focus")
    context = state.get("retrieved_context")
    llm_primary_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )

    # --- Validações ---
    if not llm_primary_instance:
        return {"error": "Certainty generation failed: LLM unavailable."}
    if not focus:
        return {"error": "Certainty generation failed: Focus not set."}
    if not profile_dict:
        return {"error": "Certainty generation failed: Missing profile dict."}
    if not messages:
        return {"error": "Certainty generation failed: Empty message history."}

    last_human_message_obj = (
        messages[-1] if messages and isinstance(messages[-1], HumanMessage) else None
    )
    last_human_message_content = getattr(last_human_message_obj, "content", "")

    logger.debug(
        f"[{node_name}] Generating statement for focus: {focus}. Context available: {bool(context)}"
    )
    logger.debug(
        f"[{node_name}] Last human message for context: '{last_human_message_content[:100]}...'"
    )

    # --- Prompt SUPER REFINADO para Saída Estruturada ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas IA de alta performance, mestre na técnica Linha Reta e em comunicação empática. Seu objetivo é construir CERTEZA no cliente de forma CONVERSACIONAL, separando a conexão da declaração principal.
O foco atual é aumentar a certeza sobre: **{focus}**.

**Contexto:**
Última Mensagem do Cliente: {last_customer_message}
Foco da Certeza: {focus}

**Instruções:**
1.  **Gere a `connection_phrase` (Opcional, mas importante):**
    *   **Analise o SENTIMENTO e CONTEÚDO** da 'Última Mensagem do Cliente'. É uma preocupação? Uma dúvida? Um interesse? Um **benefício desejado**? Um **objetivo**?
    *   Crie uma frase curta que **REFLITA ACURADAMENTE** esse sentimento/conteúdo e mostre entendimento.
        *   Se for Preocupação/Dúvida: "Entendo sua questão sobre X..." ou "Faz sentido você pensar sobre Y..."
        *   Se for Interesse: "Ótimo ponto sobre Z!" ou "Interessante você mencionar A..."
        *   **Se for Benefício Desejado/Objetivo:** "Exatamente! Conseguir [benefício desejado] é fundamental." ou "Você tocou num ponto crucial: poder [objetivo do cliente]." ou "Concordo, focar em [objetivo do cliente] faz toda a diferença."
    *   **Seja Específico:** Evite conexões genéricas como "Entendido.". Use palavras da mensagem do cliente se ajudar.
    *   Se a última mensagem foi muito simples (ex: "ok"), deixe nula/vazia.
2.  **Gere a `certainty_statement` (Obrigatório):**
    *   Crie uma declaração **específica, confiante e positiva** para o foco '{focus}'.
    *   **CONECTE a declaração ao ponto levantado pelo cliente (na `connection_phrase`)**. Mostre COMO o produto/agente/empresa ajuda a resolver a preocupação OU a alcançar o benefício/objetivo mencionado.
    *   Use o CONTEXTO ADICIONAL se relevante.
    *   **Exemplos por Foco (Conectados ao Benefício/Objetivo):**
        *   'product' (Cliente quer focar no core): "...e o [Produto] permite exatamente isso ao automatizar [processo X], liberando sua equipe para focar nas atividades estratégicas."
        *   'agent' (Cliente quer focar no core): "...e nossa equipe pode te ajudar justamente nisso, pois temos experiência em configurar a automação para que sua operação se concentre no que mais importa."
        *   'company' (Cliente quer focar no core): "...e como empresa, nosso foco é fornecer ferramentas como [Produto] que impulsionam a eficiência e permitem que nossos clientes cresçam focados no seu core business."
    *   Mantenha o tom {sales_tone}. Seja claro e direto.
    *   **NÃO FAÇA PERGUNTAS** nesta declaração.
3.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}
4.  **Output:** Responda APENAS com um objeto JSON contendo "connection_phrase" (string opcional ou null) e "certainty_statement" (string obrigatória).

PERFIL DA EMPRESA: {company_name}
CONTEXTO ADICIONAL (Use se relevante para o foco '{focus}'): {additional_context}
HISTÓRICO RECENTE (Opcional): {chat_history}

Instrução Final: Gere o JSON com "connection_phrase" e "certainty_statement" focada em '{focus}', garantindo que a conexão reflita o sentimento real do cliente.""",
            ),
        ]
    )

    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(messages[-4:-1])
        ]
    )

    # --- Cadeia com LLM Estruturado ---
    structured_llm = llm_primary_instance.with_structured_output(
        CertaintyGenerationOutput
    )
    chain = prompt_template | structured_llm

    try:
        profile = CompanyProfileSchema.model_validate(profile_dict)
    except Exception:
        profile = None
    if not profile:
        return {"error": "Certainty generation failed: Invalid profile data."}

    try:
        structured_result: CertaintyGenerationOutput = await chain.ainvoke(
            {
                "focus": focus,
                "last_customer_message": (
                    last_human_message_content if last_human_message_content else "N/A"
                ),
                "additional_context": (
                    context
                    if context
                    else "Nenhuma informação adicional específica recuperada."
                ),
                "chat_history": formatted_history if formatted_history else "N/A",
                "company_name": profile.company_name or "N/A",
                "sales_tone": profile.sales_tone or "profissional e confiante",
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )

        logger.info(
            f"[{node_name}] Structured certainty generation result: {structured_result}"
        )

        # --- Combina as partes ---
        connection = structured_result.connection_phrase
        statement = structured_result.certainty_statement

        if not statement:
            raise ValueError("LLM returned empty certainty_statement.")
        if statement.endswith("?"):
            raise ValueError("LLM included question in certainty_statement.")

        if connection and connection.strip():
            connection_formatted = connection.strip()
            generated_response = f"{connection_formatted} {statement}"
        else:
            generated_response = statement

        logger.info(
            f"[{node_name}] Combined certainty response: '{generated_response}'"
        )
        ai_message = AIMessage(content=generated_response)

        return {
            "generation": generated_response,
            "messages": [ai_message],
            "retrieved_context": None,
            "certainty_status": CERTAINTY_STATUS_STATEMENT_MADE,
            "error": None,
        }

    except Exception as e:
        # ... (Fallback como antes) ...
        logger.exception(
            f"[{node_name}] Error generating structured certainty statement: {e}"
        )
        fallback = f"Entendo. Sobre {focus}, posso afirmar que temos excelentes resultados e confiabilidade."
        ai_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_message],
            "retrieved_context": None,
            "certainty_status": None,
            "error": f"Certainty generation failed: {e}",
        }
