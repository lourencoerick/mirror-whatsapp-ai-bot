# backend/app/services/ai_reply/nodes_objection.py

from typing import Dict, Any, List, Optional, Literal
from loguru import logger
import json

# Import State and Constants
from .graph_state import ConversationState

from .graph_state import SALES_STAGE_OBJECTION_HANDLING

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
    logger.error("LangChain core not found for Objection nodes.")

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
        def from_messages(cls, *a, **k):
            return cls()

        async def ainvoke(self, *a, **k):
            return []


# Import RAG components (ou funções de repositório)
try:
    from .nodes_core import retrieve_knowledge_node  # Podemos reutilizar ou adaptar

    # Ou importar diretamente:
    # from app.core.embedding_utils import get_embedding
    # from app.services.repository.knowledge_chunk import search_similar_chunks
    # from app.models.knowledge_chunk import KnowledgeChunk
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.error("RAG components not found for Objection nodes.")

    async def retrieve_knowledge_node(state, config):
        return {"retrieved_context": None}  # Dummy


# Import Pydantic para possível output estruturado
from pydantic import BaseModel, Field

# Importar utils de prompt
from .prompt_utils import WHATSAPP_MARKDOWN_INSTRUCTIONS


# --- Schema para Análise Pós-Rebuttal ---
class ObjectionStatus(BaseModel):
    """Analysis of customer response after an objection rebuttal."""

    objection_resolved: bool = Field(
        ...,
        description="True if the customer's response indicates the previous objection is likely resolved or they are moving on.",
    )
    new_objection_raised: bool = Field(
        ...,
        description="True if the customer raised a new, different objection in their response.",
    )
    summary_new_objection: Optional[str] = Field(
        None,
        description="If new_objection_raised is true, a brief summary of the new objection.",
    )


# ==============================================================================
# Objection Handling Subgraph Nodes
# ==============================================================================


async def acknowledge_and_clarify_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Acknowledges the customer's objection empathetically and potentially asks
    a brief clarifying question before attempting a full rebuttal.
    Also extracts/summarizes the objection.

    Args:
        state: Requires 'messages'.
        config: Requires 'llm_fast'.

    Returns:
        Dict with 'generation', 'messages', and updated 'current_objection'.
    """
    node_name = "acknowledge_and_clarify_node"
    logger.info(f"--- Starting Node: {node_name} (Objection Subgraph) ---")

    messages = state.get("messages", [])
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    if not llm_fast:
        logger.exception("Objection handling failed: LLM unavailable.")
        return {"error": "Objection handling failed: LLM unavailable."}
    if not messages:
        logger.exception("Objection handling failed: No messages.")
        return {"error": "Objection handling failed: No messages."}

    # A objeção está na última mensagem do cliente
    last_human_message = (
        messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    )
    if not last_human_message:
        return {"error": "Objection handling failed: Last message not from user."}

    logger.debug(
        f"[{node_name}] Acknowledging objection in message: '{last_human_message[:100]}...'"
    )

    # Prompt para extrair a objeção e gerar reconhecimento + possível clarificação
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas empático e habilidoso em lidar com objeções.
O cliente acabou de expressar a seguinte preocupação/objeção:
"{customer_objection_text}"

Sua Tarefa:
1.  **Extraia/Resuma a Objeção Principal:** Identifique a essência da objeção do cliente em poucas palavras.
2.  **Gere uma Resposta Curta:**
    *   Comece validando o sentimento/preocupação do cliente (ex: "Entendo sua preocupação sobre...", "Faz sentido você pensar sobre...").
    *   **Opcional:** Se a objeção for vaga (ex: "Preciso pensar"), faça UMA pergunta curta para clarificar (ex: "O que especificamente te deixou com dúvidas?", "Há algo em particular que você gostaria de discutir mais?").
    *   **Se a objeção for clara (ex: preço, tempo):** NÃO faça perguntas agora, apenas valide.
    *   Mantenha um tom {sales_tone}. Use formatação WhatsApp sutil {formatting_instructions}.

Responda APENAS com um objeto JSON contendo:
- "objection_summary": (string) O resumo da objeção que você identificou.
- "acknowledgement_message": (string) A mensagem de validação/clarificação gerada.""",
            ),
        ]
    )

    # Schema para a saída estruturada
    class AckOutput(BaseModel):
        objection_summary: str = Field(
            description="Brief summary of the customer's main objection."
        )
        acknowledgement_message: str = Field(
            description="The empathetic acknowledgement/clarification message to send."
        )

    structured_llm = llm_fast.with_structured_output(AckOutput)
    chain = prompt_template | structured_llm

    try:
        profile_dict = state.get("company_profile", {})
        result: AckOutput = await chain.ainvoke(
            {
                "customer_objection_text": last_human_message,
                "sales_tone": profile_dict.get("sales_tone", "compreensivo"),
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )

        logger.info(f"[{node_name}] Objection summary: '{result.objection_summary}'")
        logger.info(
            f"[{node_name}] Acknowledgement message: '{result.acknowledgement_message}'"
        )

        ai_message = AIMessage(content=result.acknowledgement_message)

        # Atualiza o estado com a objeção identificada e a mensagem de reconhecimento
        return {
            "current_objection": result.objection_summary,  # Guarda a objeção atual
            "generation": result.acknowledgement_message,  # Mensagem a ser enviada
            "messages": [ai_message],
            "objection_loop_count": 0,  # Reseta o contador para uma nova objeção
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error acknowledging objection: {e}")
        fallback = "Entendo sua colocação. Poderia me dizer um pouco mais sobre sua preocupação?"
        ai_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_message],
            "current_objection": "Unknown",  # Define como desconhecida
            "objection_loop_count": 0,
            "error": f"Acknowledgement failed: {e}",
        }


async def retrieve_knowledge_for_objection_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Retrieves knowledge specifically relevant to the 'current_objection'.
    Reuses or adapts the core RAG logic.

    Args:
        state: Requires 'current_objection', 'account_id'.
        config: Requires 'db_session_factory'.

    Returns:
        Dictionary with 'retrieved_context' specific to the objection.
    """
    node_name = "retrieve_knowledge_for_objection_node"
    logger.info(f"--- Starting Node: {node_name} (Objection Subgraph) ---")

    objection = state.get("current_objection")
    account_id = state.get("account_id")

    if not objection:
        logger.warning(f"[{node_name}] No current objection identified. Skipping RAG.")
        return {"retrieved_context": None}
    if not RAG_AVAILABLE:
        logger.error(f"[{node_name}] RAG components unavailable. Skipping.")
        return {"retrieved_context": None}

    # Usa a objeção como base para a query RAG
    query_text = f"Como responder à objeção: {objection}"
    logger.debug(f"[{node_name}] RAG query for objection: '{query_text}'")

    # Chama o nó RAG principal ou a lógica RAG diretamente
    # Passando um estado modificado ou a query diretamente
    # Aqui, vamos simular a chamada ao nó RAG principal,
    # sobrescrevendo temporariamente o input_message para a query da objeção.
    # Uma abordagem mais limpa seria ter uma função RAG reutilizável.
    temp_state_for_rag = state.copy()
    temp_state_for_rag["input_message"] = query_text

    try:
        rag_result = await retrieve_knowledge_node(temp_state_for_rag, config)
        retrieved_context = rag_result.get("retrieved_context")
        if retrieved_context:
            logger.info(f"[{node_name}] Retrieved context for objection: '{objection}'")
            logger.trace(f"[{node_name}] Context: {retrieved_context}")
        else:
            logger.info(
                f"[{node_name}] No specific context found for objection: '{objection}'"
            )
        # Retorna apenas o contexto, não outros erros do RAG node
        return {"retrieved_context": retrieved_context}
    except Exception as e:
        logger.exception(f"[{node_name}] Error during RAG for objection: {e}")
        return {"retrieved_context": None}


async def generate_rebuttal_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Generates a persuasive rebuttal to the 'current_objection', using RAG context.

    Args:
        state: Requires 'messages', 'company_profile', 'current_objection', 'retrieved_context'.
        config: Requires 'llm_primary'.

    Returns:
        Dictionary with 'generation' and 'messages'. Increments 'objection_loop_count'.
    """
    node_name = "generate_rebuttal_node"
    logger.info(f"--- Starting Node: {node_name} (Objection Subgraph) ---")

    messages = state.get("messages", [])
    profile_dict = state.get("company_profile")
    objection = state.get("current_objection")
    context = state.get("retrieved_context")
    llm_primary: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )
    loop_count = state.get("objection_loop_count", 0)

    # --- Validações ---
    if not llm_primary:
        logger.exception("Rebuttal failed: LLM unavailable.")
        return {"error": "Rebuttal failed: LLM unavailable."}
    if not profile_dict:
        logger.exception("Rebuttal failed: Missing profile.")
        return {"error": "Rebuttal failed: Missing profile."}
    if not objection:
        logger.exception("Rebuttal failed: No objection identified.")
        return {"error": "Rebuttal failed: No objection identified."}

    logger.debug(
        f"[{node_name}] Generating rebuttal for objection: '{objection}'. Attempt: {loop_count + 1}"
    )

    # --- Prompt para Rebuttal ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas experiente em superar objeções e lidar com frustrações do cliente, usando lógica, valor e empatia genuína. **Evite soar como um script ou usar fórmulas prontas de forma rígida.**
                O cliente levantou a seguinte objeção/preocupação/frustração: **"{customer_objection}"**.

                Sua Tarefa: Gerar uma resposta natural, empática e estratégica para lidar com a situação.

                **Instruções:**

                1.  **Mostre Empatia Genuína e Específica:** Comece reconhecendo o sentimento ou a preocupação *específica* do cliente de forma natural. (Ex: "Entendo que a implementação possa parecer um ponto delicado...", "Compreendo sua necessidade de ter clareza sobre os custos futuros...", "Faz sentido você querer comparar com outras opções...").

                2.  **CASO ESPECIAL - Falta de Informação Repetida:** Se a objeção/frustração principal for sobre a **falta de uma informação específica** que você já indicou anteriormente não possuir (ex: preço futuro, case específico, plano detalhado):
                    *   **NÃO** use fórmulas genéricas como Feel-Felt-Found.
                    *   **Reafirme a Empatia:** Valide a frustração ou a importância da informação para o cliente (Ex: "Entendo perfeitamente sua necessidade de saber o preço final para poder planejar...", "Compreendo que ter cases de sucesso ajudaria na sua avaliação...").
                    *   **Reitere Brevemente a Indisponibilidade:** Mencione concisamente que a informação específica ainda não está disponível (Ex: "...e como mencionei, essa informação será definida em breve.", "...ainda estamos compilando esses dados."). **Evite apenas repetir a frase de contato padrão.**
                    *   **REDirecione Estrategicamente:** **MUITO IMPORTANTE:** Proponha ativamente uma **alternativa de valor** ou um **próximo passo concreto** que você *pode* oferecer *agora* para ajudar o cliente a avançar ou a entender melhor o valor, *apesar* da informação faltante. Exemplos de redirecionamento:
                        *   Focar em Benefícios Já Discutidos: "...Enquanto isso, podemos revisitar como a [Funcionalidade X] resolveria [Problema Y] que você mencionou? Isso já traria [Benefício Z] para sua operação."
                        *   Oferecer Ação Concreta: "...Posso te ajudar agendando uma demonstração personalizada para você ver o produto em ação?"
                        *   Aprofundar em Outro Ponto de Valor: "...Gostaria de explorar em mais detalhes como funciona o nosso painel de métricas para acompanhamento?"
                        *   Perguntar sobre Prioridades: "...Considerando as informações que já temos, qual o aspecto mais crítico que você precisa resolver neste momento?"

                3.  **Abordagem para Objeções "Reais" (Se NÃO for falta de informação):**
                    *   **Use o Contexto (RAG):** Se houver 'Informações Relevantes', use-as para embasar sua resposta com fatos, dados ou exemplos que abordem a objeção.
                    *   **Aborde a Preocupação Central:** Responda diretamente à lógica ou emoção por trás da objeção (re-enquadre valor, esclareça mal-entendidos, apresente soluções, use prova social do contexto).
                    *   **Construa Confiança:** Se a objeção for sobre a empresa ou o agente, use informações do contexto para reforçar a credibilidade.

                4.  **Mantenha o Tom:** Use um tom {sales_tone}, que seja confiante, mas também compreensivo e colaborativo. Adapte o tom ligeiramente dependendo se é uma objeção real ou frustração por falta de info.

                5.  **Termine com Verificação/Avanço Suave:** Após a refutação ou redirecionamento, faça uma pergunta curta e aberta para verificar o entendimento ou propor um próximo passo suave, alinhado com a sua resposta. (Ex: "Isso faz sentido para você?", "O que acha dessa alternativa?", "Podemos seguir por esse caminho então?").

                6.  **Formatação:** Aplique formatação WhatsApp sutil. {formatting_instructions}

                **INFORMAÇÕES RELEVANTES (RAG):**
                {relevant_context}

                **HISTÓRICO RECENTE:**
                {chat_history}

                **Instrução Final:** Gere uma resposta empática, estratégica e persuasiva para a objeção/frustração '{customer_objection}', seguindo os princípios e casos acima.
                """,
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
    chain = prompt_template | llm_primary | parser

    try:
        rebuttal_response = await chain.ainvoke(
            {
                "customer_objection": objection,
                "relevant_context": (
                    context if context else "Nenhuma informação específica encontrada."
                ),
                "chat_history": formatted_history if formatted_history else "N/A",
                "sales_tone": profile_dict.get("sales_tone", "confiante e prestativo"),
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )
        rebuttal_response = rebuttal_response.strip()

        if not rebuttal_response:
            raise ValueError("LLM returned empty rebuttal.")

        logger.info(f"[{node_name}] Generated rebuttal: '{rebuttal_response[:100]}...'")
        ai_message = AIMessage(content=rebuttal_response)

        # Incrementa o contador de loop para esta objeção
        return {
            "generation": rebuttal_response,
            "messages": [ai_message],
            "objection_loop_count": loop_count + 1,  # Incrementa
            "retrieved_context": None,  # Limpa contexto RAG usado
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating rebuttal: {e}")
        fallback = (
            "Entendo sua preocupação. Gostaria de discutir outras opções ou benefícios?"
        )
        ai_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_message],
            "objection_loop_count": loop_count
            + 1,  # Incrementa mesmo em erro para evitar loop infinito
            "retrieved_context": None,
            "error": f"Rebuttal generation failed: {e}",
        }


# --- Função Condicional para Roteamento Pós-Rebuttal ---
async def check_objection_resolved_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Analyzes the customer's response after a rebuttal using an LLM to determine
    if the objection is resolved, persists, or if a new one was raised.
    Also checks loop count.

    Args:
        state: Requires 'messages', 'objection_loop_count', 'current_objection'.
        config: Requires 'llm_fast'.

    Returns:
        Dictionary updating 'objection_resolution_status' and potentially resetting
        'current_objection' and 'objection_loop_count'.
    """
    node_name = "check_objection_resolved_node"
    logger.info(f"--- Starting Node: {node_name} (Objection Subgraph) ---")

    messages = state.get("messages", [])
    loop_count = state.get("objection_loop_count", 0)
    current_objection = state.get(
        "current_objection", "a objeção anterior"
    )  # Pega objeção tratada
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )
    max_loops = 2  # Limite de tentativas

    # --- Verificação de Loop ---
    if loop_count >= max_loops:
        logger.warning(
            f"[{node_name}] Objection handling loop limit ({max_loops}) reached for '{current_objection}'. Exiting loop."
        )
        return {
            "current_objection": None,  # Limpa objeção atual
            "objection_loop_count": 0,  # Reseta contador
            "objection_resolution_status": "LOOP_LIMIT_EXIT",  # Status específico
            "error": None,
        }

    # --- Validações ---
    if not llm_fast:
        return {"error": "Objection check failed: LLM unavailable."}
    if not messages or len(messages) < 2:
        return {"error": "Objection check failed: Not enough context."}

    # Pega a última resposta do cliente e o rebuttal do agente
    last_human_message = (
        messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    )
    last_ai_rebuttal = (
        messages[-2].content
        if len(messages) >= 2 and isinstance(messages[-2], AIMessage)
        else ""
    )

    if not last_human_message:
        return {"error": "Objection check failed: Last message not from user."}

    logger.debug(
        f"[{node_name}] Checking resolution for objection '{current_objection}' after rebuttal."
    )
    logger.debug(f"[{node_name}] Last Rebuttal: '{last_ai_rebuttal[:100]}...'")
    logger.debug(f"[{node_name}] Customer Response: '{last_human_message[:100]}...'")

    # --- Prompt para Análise da Resposta ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um analista de vendas. O agente acabou de tentar responder à objeção do cliente. Analise a RESPOSTA DO CLIENTE.

Objeção Anterior: {previous_objection}
Resposta do Agente (Rebuttal): {agent_rebuttal}
Resposta do Cliente AGORA: {customer_response}

Determine o status da objeção:
1.  `objection_resolved`: A resposta do cliente indica que a objeção anterior foi superada ou ele está seguindo em frente? (true/false)
2.  `new_objection_raised`: A resposta do cliente introduz uma *nova* e *diferente* objeção? (true/false)
3.  `summary_new_objection`: Se `new_objection_raised` for true, resuma a nova objeção. Senão, null.

Responda APENAS com um objeto JSON seguindo o schema ObjectionStatus.""",
            ),
        ]
    )

    # --- Cadeia com LLM Estruturado ---
    structured_llm = llm_fast.with_structured_output(ObjectionStatus)
    chain = prompt_template | structured_llm

    try:
        analysis_result: ObjectionStatus = await chain.ainvoke(
            {
                "previous_objection": current_objection,
                "agent_rebuttal": last_ai_rebuttal,
                "customer_response": last_human_message,
            }
        )
        logger.info(
            f"[{node_name}] Objection status analysis result: {analysis_result}"
        )

        # --- Determina o Status Final ---
        status_to_return = "PERSISTS"  # Default se não resolvido e sem nova objeção
        new_objection_summary = None
        reset_loop_count = False

        if analysis_result.objection_resolved:
            status_to_return = "RESOLVED"
            reset_loop_count = True  # Objeção resolvida, reseta contador
            logger.info(
                f"[{node_name}] Objection '{current_objection}' determined as RESOLVED."
            )
        elif (
            analysis_result.new_objection_raised
            and analysis_result.summary_new_objection
        ):
            status_to_return = "NEW_OBJECTION"
            new_objection_summary = analysis_result.summary_new_objection
            reset_loop_count = True  # Nova objeção, reseta contador para ela
            logger.info(
                f"[{node_name}] NEW objection identified: '{new_objection_summary}'."
            )
        else:
            logger.info(f"[{node_name}] Objection '{current_objection}' PERSISTS.")

        # Retorna o status e atualiza/reseta estado da objeção
        return {
            "objection_resolution_status": status_to_return,
            # Atualiza current_objection se uma nova foi encontrada, senão limpa se resolvida/limite
            "current_objection": (
                new_objection_summary
                if status_to_return == "NEW_OBJECTION"
                else (None if status_to_return == "RESOLVED" else current_objection)
            ),
            "objection_loop_count": (
                0 if reset_loop_count else loop_count
            ),  # Reseta ou mantém
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error during objection resolution check: {e}")
        # Em caso de erro na análise, assume que persiste e não reseta contador
        return {
            "objection_resolution_status": "PERSISTS_ERROR",
            "objection_loop_count": loop_count,  # Mantém contador atual
            "error": f"Objection resolution check failed: {e}",
        }
