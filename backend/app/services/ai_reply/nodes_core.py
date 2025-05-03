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
    CompanyProfileSchema,
    BotAgentRead,
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
]

from pydantic import BaseModel, Field


# --- Pydantic Schema for Intent/Stage Classification Output ---
class IntentStageClassificationOutput(BaseModel):
    """Structured output for intent and sales stage classification."""

    intent: str = Field(
        ...,
        description=f"The primary intent of the customer's last message. Valid intents: {VALID_INTENTS}",
    )
    next_sales_stage: str = Field(
        ...,
        description=f"The recommended next sales stage based on the conversation. Valid stages: {VALID_SALES_STAGES}",
    )


# ==============================================================================
# Core Graph Nodes
# ==============================================================================


async def classify_intent_and_stage_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Uses an LLM with structured output to classify intent and determine the next sales stage.

    Args:
        state: The current conversation state. Requires 'messages'.
        config: The graph configuration. Requires 'llm_fast_instance'.

    Returns:
        A dictionary containing 'intent', 'current_sales_stage', and optionally 'error'.
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
        logger.warning(
            f"[{node_name}] No messages in state. Defaulting stage to Opening."
        )
        return {
            "intent": "Unknown",
            "current_sales_stage": SALES_STAGE_OPENING,
            "error": None,
        }

    history_for_classification = messages[-10:]
    last_message = history_for_classification[-1]
    last_message_content = (
        getattr(last_message, "content", "")
        if isinstance(getattr(last_message, "content", ""), str)
        else ""
    )

    if not last_message_content:
        logger.warning(
            f"[{node_name}] Last message has no text content. Cannot classify."
        )
        return {
            "intent": "Unknown",
            "current_sales_stage": previous_stage or SALES_STAGE_OPENING,
            "error": None,
        }

    logger.debug(
        f"[{node_name}] Classifying message: '{last_message_content[:100]}...'"
    )
    logger.debug(f"[{node_name}] Previous stage was: {previous_stage}")

    # --- Prompt de Classificação  ---
    classification_prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um especialista em análise de conversas de vendas. Analise a ÚLTIMA MENSAGEM do cliente no contexto do HISTÓRICO DA CONVERSA e do ESTÁGIO ANTERIOR da venda.
Sua tarefa é classificar a INTENÇÃO do cliente e determinar o PRÓXIMO ESTÁGIO da venda.

Estágios de Venda Possíveis: {valid_stages}
Intenções Possíveis: {valid_intents}

Considere o seguinte:
- Se for o início ou saudações, estágio é 'Opening'.
- Se o cliente faz perguntas gerais/específicas ou descreve problemas/situação após a abertura, o estágio deve ser 'Investigation'. **Mantenha 'Investigation' mesmo que o cliente mencione um problema ou interesse inicial.**
- Mude para 'Presentation' SOMENTE se o cliente, após uma pergunta focada em benefícios (Need-Payoff), **confirmar explicitamente o valor** ou pedir para ver a solução (ex: "Sim, isso seria ótimo!", "Como funciona na prática?", "Me mostre como fazer X"). Uma simples menção a um problema ou funcionalidade NÃO é suficiente para ir para 'Presentation'.
- Se o cliente expressa dúvidas claras sobre preço, tempo, valor, etc., é 'ObjectionHandling'.
- Se o cliente demonstra claro interesse em comprar ou pergunta como proceder, é 'Closing'.
- Se a conversa parece desviada ou a intenção não é clara, use 'Unknown' ou mantenha o estágio anterior.

HISTÓRICO DA CONVERSA: {chat_history}
ESTÁGIO ANTERIOR: {previous_stage}
FLAG NECESSIDADE EXPLÍCITA IDENTIFICADA (do ciclo SPIN anterior): {explicit_need_identified}
ÚLTIMA MENSAGEM DO CLIENTE: {last_message}

Classifique a intenção e o próximo estágio.""",
            ),
        ]
    )

    # Formata o histórico
    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(history_for_classification[:-1])
        ]
    )
    logger.debug("[{node_name}]Conversation History: {formatted_history} ")
    # --- Cria LLM Estruturado ---
    structured_llm = llm_fast_instance.with_structured_output(
        IntentStageClassificationOutput
    )

    try:
        logger.debug(f"[{node_name}] Invoking structured classification chain...")

        prompt_filled = classification_prompt_template.format_messages(
            valid_stages=", ".join(VALID_SALES_STAGES),
            valid_intents=", ".join(VALID_INTENTS),
            chat_history=formatted_history or "N/A",
            previous_stage=previous_stage or "None",
            last_message=last_message_content,
            explicit_need_identified=str(explicit_need_identified).upper(),
        )
        logger.info(f"[{node_name}] Prompt used: {prompt_filled} ")
        classification_result: IntentStageClassificationOutput = (
            await structured_llm.ainvoke(prompt_filled)
        )
        logger.info(
            f"[{node_name}] Structured classification result: {classification_result}"
        )

        # --- Validação (Opcional - Pydantic já validou tipos/campos obrigatórios) ---
        intent = classification_result.intent
        next_stage = classification_result.next_sales_stage

        if intent not in VALID_INTENTS:
            logger.warning(
                f"[{node_name}] LLM returned intent '{intent}' not in VALID_INTENTS. Defaulting to Unknown."
            )
            intent = "Unknown"
        if next_stage not in VALID_SALES_STAGES:
            logger.warning(
                f"[{node_name}] LLM returned stage '{next_stage}' not in VALID_SALES_STAGES. Defaulting."
            )
            next_stage = previous_stage or SALES_STAGE_UNKNOWN

        return {
            "intent": intent,
            "current_sales_stage": next_stage,
            "classification_details": classification_result.model_dump(),
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


async def transition_after_answer_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates ONLY the transition question/hook after the agent has answered
    a direct question via generate_response_node.

    Args:
        state: Current state. Requires 'messages', 'current_sales_stage'.
        config: Requires 'llm_fast'.

    Returns:
        Dictionary with 'generation' (the transition question) and 'messages'
        (the transition question as an AIMessage).
    """
    node_name = "transition_after_answer_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    messages = state.get("messages", [])
    current_stage = state.get("current_sales_stage")
    previous_generation = state.get("generation", "")

    # Pega a pergunta original do cliente para contexto
    last_human_message = (
        messages[-2].content
        if len(messages) >= 2 and isinstance(messages[-2], HumanMessage)
        else ""
    )
    # Pega a resposta que o agente deu (última mensagem no estado atual)
    last_agent_response = (
        messages[-1].content if messages and isinstance(messages[-1], AIMessage) else ""
    )

    llm_fast_instance: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    if not llm_fast_instance:
        return {"error": "Transition failed: LLM unavailable."}
    elif not previous_generation:
        logger.warning(
            f"[{node_name}] No previous generation found in state. Ending turn."
        )
        return {}
    if len(messages) < 2:
        logger.warning(
            f"[{node_name}] Not enough context to generate transition. Skipping."
        )
        return {}  # Retorna vazio para não adicionar nada

    logger.debug(
        f"[{node_name}] Generating transition hook after agent response: '{last_agent_response[:50]}...'"
    )

    # --- Prompt para gerar APENAS a pergunta de transição ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas que acabou de responder à pergunta do cliente.
                Sua tarefa agora é fazer uma **transição suave** para retomar o controle e continuar a investigação (Estágio Atual: {current_stage}).

                **Contexto:**
                Pergunta do Cliente: {last_human_message}
                Sua Resposta Anterior (Resumo): {last_agent_response_summary}

                **Instruções:**
                1.  **Reconheça (Opcional):** Comece com uma frase curta confirmando se a resposta anterior foi útil (ex: "Isso ajudou a esclarecer?", "Fez sentido?").
                2.  **Conecte e Pergunte:** Faça UMA pergunta relevante que:
                    *   Se conecte à **resposta que você deu** (ex: "Qual dessas funcionalidades mais te interessou?") OU
                    *   Se conecte à **pergunta original do cliente** (ex: "Além disso que perguntei, qual era o principal desafio que você tinha em mente?") OU
                    *   Seja uma pergunta de **Problema ou Implicação SPIN** apropriada para o estágio de Investigação.
                3.  **Seja Natural e Conciso:** Evite perguntas genéricas demais. Tente fazer a conversa fluir.
                4.  **Formatação:** Use formatação WhatsApp sutilmente, se necessário (ex: *negrito* para um termo chave na pergunta).

                Gere APENAS a frase de reconhecimento (opcional) + a pergunta de transição.""",
            ),
        ]
    )

    parser = StrOutputParser()
    chain = prompt_template | llm_fast_instance | parser

    try:
        response_summary = (
            last_agent_response[:150] + "..."
            if len(last_agent_response) > 150
            else last_agent_response
        )

        transition_question = await chain.ainvoke(
            {
                "current_stage": current_stage or SALES_STAGE_INVESTIGATION,
                "last_human_message": last_human_message or "N/A",
                "last_agent_response_summary": response_summary,
            }
        )
        transition_question = transition_question.strip()

        if not transition_question or not transition_question.endswith("?"):
            logger.warning(
                f"[{node_name}] LLM generated invalid transition: '{transition_question}'. Skipping transition."
            )
            return {}  # Não retorna erro, apenas não faz a transição

        logger.info(
            f"[{node_name}] Generated transition question: '{transition_question}'"
        )

        # --- COMBINA a resposta anterior com a nova pergunta ---
        final_response_text = f"{previous_generation}\n\n{transition_question}"
        # --- FIM COMBINAÇÃO ---

        ai_message = AIMessage(
            content=transition_question
        )  # Mensagem SÓ com a pergunta

        # Atualiza 'generation' com a pergunta e 'messages' com a AIMessage dela
        return {
            "generation": final_response_text,  # <-- Generation é SÓ a pergunta
            "messages": [
                ai_message
            ],  # <-- Adiciona SÓ a pergunta ao histórico do grafo
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating transition question: {e}")
        return {"error": f"Transition generation failed: {e}"}
