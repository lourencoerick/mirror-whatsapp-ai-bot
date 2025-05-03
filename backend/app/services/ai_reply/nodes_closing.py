from typing import Dict, Any, Optional, Literal
from loguru import logger
from pydantic import BaseModel, Field

# Import State and Constants
from .graph_state import (
    ConversationState,
    SALES_STAGE_CLOSING,
    SALES_STAGE_PRESENTATION,
)
from .prompt_utils import WHATSAPP_MARKDOWN_INSTRUCTIONS

# Import LLM and related components
try:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from trustcall import (
        create_extractor,
    )  # Usaremos trustcall para extração estruturada aqui

    LANGCHAIN_CORE_AVAILABLE = True
    TRUSTCALL_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    TRUSTCALL_AVAILABLE = False
    logger.error("LangChain core or trustcall not found for Closing nodes.")

    # Dummy classes if needed
    class BaseChatModel:
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

    async def create_extractor(*args, **kwargs):
        raise ImportError("trustcall not installed")


# --- Pydantic Schema for Closing Response Analysis ---
class ClosingResponseAnalysisOutput(BaseModel):
    """Structured output for analyzing customer response to a closing attempt."""

    response_type: Literal[
        "CONFIRMED", "OBJECTION", "QUESTION", "UNCERTAIN", "OTHER"
    ] = Field(
        ...,
        description="Classify the customer's response type: CONFIRMED (agrees to proceed), OBJECTION (raises barrier/hesitation), QUESTION (asks for clarification), UNCERTAIN (hesitant, needs time), OTHER.",
    )
    objection_summary: Optional[str] = Field(
        None,
        description="If response_type is OBJECTION or UNCERTAIN, provide a brief summary of the objection/hesitation.",
    )


class ConfirmationResponseAnalysisOutput(BaseModel):
    """Structured output for analyzing customer response to order confirmation."""

    confirmation_type: Literal["YES", "NO", "CORRECTION"] = Field(
        ...,
        description="Classify the customer's response: YES (confirms details), NO (rejects/cancels), CORRECTION (wants changes).",
    )
    correction_details: Optional[str] = Field(
        None,
        description="If confirmation_type is CORRECTION, summarize the requested changes.",
    )


# ==============================================================================
# Closing Subgraph Nodes
# ==============================================================================


async def initiate_close_node(state: ConversationState, config: dict) -> Dict[str, Any]:
    """
    Generates the initial closing question or statement.
    Sets closing_status to 'ATTEMPT_MADE'.
    (Código anterior omitido para brevidade - permanece o mesmo, mas adiciona status)
    """
    node_name = "initiate_close_node"
    logger.info(f"--- Starting Node: {node_name} (Closing Subgraph) ---")

    messages = state.get("messages", [])
    profile_dict = state.get("company_profile")
    solution_details = state.get("proposed_solution_details")
    llm_primary: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )
    attempt_count = state.get("closing_attempt_count", 0)

    # --- Validations ---
    if not llm_primary:
        return {"error": "Closing initiation failed: LLM unavailable."}
    if not profile_dict:
        return {"error": "Closing initiation failed: Missing profile."}
    if not messages:
        return {"error": "Closing initiation failed: Empty message history."}

    logger.debug(f"[{node_name}] Initiating closing attempt #{attempt_count + 1}.")
    if solution_details:
        logger.debug(f"[{node_name}] Proposed solution: {solution_details}")
    else:
        logger.warning(f"[{node_name}] No proposed solution details found in state.")

    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas experiente, pronto para fechar o negócio.
A conversa chegou a um ponto onde o cliente demonstrou necessidade e a solução foi apresentada (ou a certeza está alta).
Sua tarefa é iniciar o processo de fechamento de forma natural e confiante.

**Contexto:**
- Empresa: {company_name}
- Tom de Vendas: {sales_tone}
- Solução Discutida (se disponível): {solution_summary}

**Instruções:**
1.  **Reconheça o Momento:** Comece com uma frase curta que indique que é hora de avançar (ex: "Com base no que conversamos...", "Parece que encontramos uma boa solução...", "Ótimo, então...").
2.  **Faça a Pergunta/Afirmação de Fechamento:**
    *   Pode ser uma pergunta direta: "Podemos prosseguir com o pedido?", "Gostaria de finalizar a compra agora?", "Quais são os próximos passos para você começar?"
    *   Pode ser um fechamento por alternativa: "Você prefere a opção A ou B para começar?" (se aplicável)
    *   Pode ser um fechamento por presunção suave: "Para confirmar os detalhes do seu pedido..." (implica que o pedido vai acontecer)
    *   **Adapte ao tom {sales_tone}**: Se for 'agressivo', seja mais direto. Se for 'consultivo', mais suave.
3.  **Seja Claro e Conciso:** Evite rodeios.
4.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Instrução Final: Gere a mensagem para iniciar o fechamento.""",
            ),
        ]
    )

    formatted_history = "\n".join(
        [
            f"{'Cliente' if isinstance(m, HumanMessage) else 'Agente'}: {m.content}"
            for m in reversed(messages[-4:])
        ]
    )
    solution_summary_str = (
        str(solution_details) if solution_details else "Solução geral discutida"
    )

    parser = StrOutputParser()
    chain = prompt_template | llm_primary | parser

    try:
        closing_statement = await chain.ainvoke(
            {
                "company_name": profile_dict.get("company_name", "Nossa Empresa"),
                "sales_tone": profile_dict.get("sales_tone", "confiante"),
                "solution_summary": solution_summary_str,
                "chat_history": formatted_history if formatted_history else "N/A",
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )
        closing_statement = closing_statement.strip()

        if not closing_statement:
            raise ValueError("LLM returned empty closing statement.")

        logger.info(
            f"[{node_name}] Generated closing statement: '{closing_statement[:100]}...'"
        )
        ai_message = AIMessage(content=closing_statement)

        # <<< ADICIONA ATUALIZAÇÃO DE STATUS >>>
        return {
            "generation": closing_statement,
            "messages": [ai_message],
            "closing_attempt_count": attempt_count + 1,
            "current_sales_stage": SALES_STAGE_CLOSING,
            "closing_status": "ATTEMPT_MADE",  # <-- NOVO STATUS
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating closing statement: {e}")
        fallback = "Podemos prosseguir com os próximos passos?"
        ai_message = AIMessage(content=fallback)
        # <<< ADICIONA ATUALIZAÇÃO DE STATUS >>>
        return {
            "generation": fallback,
            "messages": [ai_message],
            "closing_attempt_count": attempt_count + 1,
            "current_sales_stage": SALES_STAGE_CLOSING,
            "closing_status": "ATTEMPT_MADE",  # <-- NOVO STATUS
            "error": f"Closing initiation failed: {e}",
        }


async def analyze_closing_response_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Analyzes the customer's response after a closing attempt using an LLM with
    structured output (trustcall).

    Args:
        state: Requires 'messages'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary updating 'closing_status' and potentially 'current_objection'.
    """
    node_name = "analyze_closing_response_node"
    logger.info(f"--- Starting Node: {node_name} (Closing Subgraph) ---")

    messages = state.get("messages", [])
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validations ---
    if not TRUSTCALL_AVAILABLE or not llm_fast:
        logger.error(f"[{node_name}] Trustcall or LLM unavailable.")
        return {
            "error": "Closing analysis failed: Dependencies missing.",
            "closing_status": "ANALYSIS_FAILED",
        }
    if not messages or len(messages) < 2:
        logger.warning(f"[{node_name}] Not enough message history for analysis.")
        # Assume uncertainty if not enough context? Or just fail? Let's fail for now.
        return {
            "error": "Closing analysis failed: Not enough history.",
            "closing_status": "ANALYSIS_FAILED",
        }

    # Get last user message and the AI's closing attempt
    last_human_message = (
        messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    )
    last_ai_closing_attempt = (
        messages[-2].content if isinstance(messages[-2], AIMessage) else ""
    )

    if not last_human_message:
        logger.warning(f"[{node_name}] Last message not from user. Cannot analyze.")
        return {
            "error": "Closing analysis failed: Last message not from user.",
            "closing_status": "ANALYSIS_FAILED",
        }

    logger.debug(
        f"[{node_name}] Analyzing customer response: '{last_human_message[:100]}...'"
    )
    logger.debug(
        f"[{node_name}] After closing attempt: '{last_ai_closing_attempt[:100]}...'"
    )

    # --- Prompt for Analysis ---
    analysis_prompt = f"""Você é um analista de vendas. O agente tentou fechar a venda. Analise a RESPOSTA DO CLIENTE.

Tentativa de Fechamento do Agente: {last_ai_closing_attempt}
Resposta do Cliente AGORA: {last_human_message}

Classifique a resposta do cliente em uma das seguintes categorias:
- CONFIRMED: Cliente concorda em prosseguir com a compra/próximo passo.
- OBJECTION: Cliente levanta uma barreira, custo, dúvida específica, ou pede mais tempo de forma hesitante.
- QUESTION: Cliente faz uma pergunta clara sobre o processo de fechamento, produto, preço final, etc.
- UNCERTAIN: Cliente expressa incerteza geral, diz que precisa pensar, mas sem uma objeção clara.
- OTHER: Não se encaixa nas categorias acima.

Se for OBJECTION ou UNCERTAIN, forneça um resumo breve da objeção/hesitação em 'objection_summary'.

Responda APENAS com o objeto JSON correspondente a ClosingResponseAnalysisOutput."""

    try:
        logger.debug(f"[{node_name}] Creating trustcall extractor...")
        extractor = create_extractor(
            llm=llm_fast,
            tools=[ClosingResponseAnalysisOutput],
            tool_choice=ClosingResponseAnalysisOutput.__name__,
        )

        logger.debug(f"[{node_name}] Invoking trustcall extractor...")
        result = await extractor.ainvoke(analysis_prompt)
        logger.debug(f"[{node_name}] Raw result from trustcall: {result}")

        responses = result.get("responses")
        if isinstance(responses, list) and len(responses) > 0:
            analysis: ClosingResponseAnalysisOutput = responses[0]
            if isinstance(analysis, ClosingResponseAnalysisOutput):
                logger.info(f"[{node_name}] Closing response analysis: {analysis}")

                status_map = {
                    "CONFIRMED": "CONFIRMED",
                    "OBJECTION": "PENDING_OBJECTION",
                    "QUESTION": "PENDING_QUESTION",  # Tratar como objeção por enquanto
                    "UNCERTAIN": "PENDING_OBJECTION",  # Tratar como objeção por enquanto
                    "OTHER": "ANALYSIS_FAILED",  # Ou um status 'NEEDS_CLARIFICATION'?
                }
                new_status = status_map.get(analysis.response_type, "ANALYSIS_FAILED")

                # Prepara o output para o estado
                output_state = {"closing_status": new_status, "error": None}
                if (
                    analysis.response_type in ["OBJECTION", "UNCERTAIN"]
                    and analysis.objection_summary
                ):
                    output_state["current_objection"] = analysis.objection_summary
                    logger.info(
                        f"[{node_name}] Objection/Hesitation identified: {analysis.objection_summary}"
                    )
                else:
                    # Limpa objeção anterior se não for mais relevante
                    output_state["current_objection"] = None

                return output_state
            else:
                raise TypeError(
                    f"Trustcall returned unexpected data type: {type(analysis)}"
                )
        else:
            raise ValueError(
                "Trustcall extraction failed to produce expected response list."
            )

    except Exception as e:
        logger.exception(f"[{node_name}] Error during closing response analysis: {e}")
        return {
            "closing_status": "ANALYSIS_FAILED",
            "current_objection": None,
            "error": f"Closing analysis failed: {e}",
        }


async def confirm_order_details_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Summarizes the proposed order details and asks for final confirmation.
    Sets closing_status to 'AWAITING_FINAL_CONFIRMATION'.

    Args:
        state: Requires 'messages', 'company_profile', 'proposed_solution_details'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with 'generation', 'messages', and updated 'closing_status'.
    """
    node_name = "confirm_order_details_node"
    logger.info(f"--- Starting Node: {node_name} (Closing Subgraph) ---")

    messages = state.get("messages", [])
    profile_dict = state.get("company_profile")
    solution_details = state.get("proposed_solution_details")
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validations ---
    if not llm_fast:
        return {"error": "Order confirmation failed: LLM unavailable."}
    if not profile_dict:
        return {"error": "Order confirmation failed: Missing profile."}
    if not solution_details or not isinstance(solution_details, dict):
        logger.error(
            f"[{node_name}] Missing or invalid proposed_solution_details in state."
        )
        return {"error": "Order confirmation failed: Missing solution details."}

    logger.debug(
        f"[{node_name}] Generating confirmation message for: {solution_details}"
    )

    # --- Format Order Summary ---
    # Basic example, adjust based on actual structure of solution_details
    summary_parts = []
    if "product_name" in solution_details:
        summary_parts.append(f"Produto: *{solution_details['product_name']}*")
    if "quantity" in solution_details:
        summary_parts.append(f"Quantidade: {solution_details['quantity']}")
    if "price" in solution_details:
        # Add currency formatting if needed
        summary_parts.append(
            f"Preço Total: R$ {solution_details['price']:.2f}"
        )  # Example formatting
    if "delivery_info" in solution_details:
        summary_parts.append(f"Entrega: {solution_details['delivery_info']}")

    order_summary = "\n".join(summary_parts)
    if not order_summary:
        order_summary = "os detalhes que discutimos"  # Fallback

    # --- Prompt for Confirmation Message ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas finalizando um pedido.
Sua tarefa é apresentar um resumo claro do pedido e pedir a confirmação final do cliente.

**Resumo do Pedido:**
{order_summary}

**Instruções:**
1.  **Apresente o Resumo:** Comece com uma frase como "Ótimo! Só para confirmar então:".
2.  **Inclua o Resumo:** Apresente o 'Resumo do Pedido' formatado.
3.  **Peça Confirmação:** Termine com uma pergunta direta e fechada. Exemplos: "Está tudo correto?", "Podemos confirmar com esses detalhes?", "Confirma?".
4.  **Seja Conciso:** Mantenha a mensagem curta e direta ao ponto.
5.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}

Gere a mensagem de confirmação.""",
            ),
        ]
    )

    parser = StrOutputParser()
    chain = prompt_template | llm_fast | parser

    try:
        confirmation_message = await chain.ainvoke(
            {
                "order_summary": order_summary,
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )
        confirmation_message = confirmation_message.strip()

        if not confirmation_message:
            raise ValueError("LLM returned empty confirmation message.")

        logger.info(
            f"[{node_name}] Generated confirmation message: '{confirmation_message[:100]}...'"
        )
        ai_message = AIMessage(content=confirmation_message)

        return {
            "generation": confirmation_message,
            "messages": [ai_message],
            "closing_status": "AWAITING_FINAL_CONFIRMATION",  # <-- NOVO STATUS
            "error": None,
        }

    except Exception as e:
        logger.exception(f"[{node_name}] Error generating confirmation message: {e}")
        fallback = (
            f"Podemos confirmar os seguintes detalhes?\n{order_summary}\nConfirma?"
        )
        ai_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_message],
            "closing_status": "AWAITING_FINAL_CONFIRMATION",
            "error": f"Order confirmation failed: {e}",
        }


async def analyze_confirmation_response_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Analyzes the customer's response to the order confirmation message using trustcall.

    Args:
        state: Requires 'messages'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary updating 'closing_status' and potentially 'correction_details'.
    """
    node_name = "analyze_confirmation_response_node"
    logger.info(f"--- Starting Node: {node_name} (Closing Subgraph) ---")

    messages = state.get("messages", [])
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validations ---
    if not TRUSTCALL_AVAILABLE or not llm_fast:
        return {
            "error": "Confirmation analysis failed: Dependencies missing.",
            "closing_status": "CONFIRMATION_FAILED",
        }
    if not messages or len(messages) < 2:
        return {
            "error": "Confirmation analysis failed: Not enough history.",
            "closing_status": "CONFIRMATION_FAILED",
        }

    last_human_message = (
        messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    )
    last_ai_confirmation = (
        messages[-2].content if isinstance(messages[-2], AIMessage) else ""
    )

    if not last_human_message:
        return {
            "error": "Confirmation analysis failed: Last message not from user.",
            "closing_status": "CONFIRMATION_FAILED",
        }

    logger.debug(
        f"[{node_name}] Analyzing confirmation response: '{last_human_message[:100]}...'"
    )
    logger.debug(
        f"[{node_name}] After confirmation request: '{last_ai_confirmation[:100]}...'"
    )

    # --- Prompt for Analysis ---
    analysis_prompt = f"""Você é um analista de vendas. O agente pediu a confirmação final dos detalhes do pedido. Analise a RESPOSTA DO CLIENTE.

Pedido de Confirmação do Agente: {last_ai_confirmation}
Resposta do Cliente AGORA: {last_human_message}

Classifique a resposta do cliente:
- YES: Cliente confirma que os detalhes estão corretos (ex: "sim", "correto", "confirmo", "pode seguir").
- NO: Cliente nega, cancela ou desiste (ex: "não", "cancela", "não quero mais").
- CORRECTION: Cliente indica que algo está errado ou precisa ser alterado (ex: "o preço está diferente", "preciso mudar a quantidade", "o endereço não é esse").

Se for CORRECTION, resuma a mudança solicitada em 'correction_details'.

Responda APENAS com o objeto JSON correspondente a ConfirmationResponseAnalysisOutput."""

    try:
        logger.debug(f"[{node_name}] Creating trustcall extractor for confirmation...")
        extractor = create_extractor(
            llm=llm_fast,
            tools=[ConfirmationResponseAnalysisOutput],
            tool_choice=ConfirmationResponseAnalysisOutput.__name__,
        )

        logger.debug(f"[{node_name}] Invoking trustcall extractor...")
        result = await extractor.ainvoke(analysis_prompt)
        logger.debug(f"[{node_name}] Raw result from trustcall: {result}")

        responses = result.get("responses")
        if isinstance(responses, list) and len(responses) > 0:
            analysis: ConfirmationResponseAnalysisOutput = responses[0]
            if isinstance(analysis, ConfirmationResponseAnalysisOutput):
                logger.info(f"[{node_name}] Confirmation response analysis: {analysis}")

                status_map = {
                    "YES": "FINAL_CONFIRMED",
                    "NO": "CONFIRMATION_REJECTED",
                    "CORRECTION": "NEEDS_CORRECTION",
                }
                new_status = status_map.get(
                    analysis.confirmation_type, "CONFIRMATION_FAILED"
                )

                output_state = {"closing_status": new_status, "error": None}
                if (
                    analysis.confirmation_type == "CORRECTION"
                    and analysis.correction_details
                ):
                    # Guardar detalhes da correção para um futuro nó 'handle_correction'
                    output_state["correction_details"] = analysis.correction_details
                    logger.info(
                        f"[{node_name}] Correction requested: {analysis.correction_details}"
                    )
                else:
                    output_state["correction_details"] = None

                return output_state
            else:
                raise TypeError(
                    f"Trustcall returned unexpected data type: {type(analysis)}"
                )
        else:
            raise ValueError(
                "Trustcall extraction failed to produce expected response list."
            )

    except Exception as e:
        logger.exception(
            f"[{node_name}] Error during confirmation response analysis: {e}"
        )
        return {
            "closing_status": "CONFIRMATION_FAILED",
            "correction_details": None,
            "error": f"Confirmation analysis failed: {e}",
        }


async def process_order_node(state: ConversationState, config: dict) -> Dict[str, Any]:
    """
    Generates a final confirmation message after the order is (theoretically) processed.
    This is a simplified version, not interacting with external systems yet.
    Sets closing_status to 'ORDER_PROCESSED'.

    Args:
        state: Current state.
        config: Graph config.

    Returns:
        Dictionary with 'generation' and 'messages'.
    """
    node_name = "process_order_node"
    logger.info(f"--- Starting Node: {node_name} (Closing Subgraph - Simplified) ---")

    # In a real scenario, this node would be a Tool calling our FastAPI backend.
    # It would receive order details from the state and return success/failure.

    # Simplified message:
    final_message = "Perfeito! Pedido confirmado. Excelente aquisição! 🎉"
    # Poderíamos adicionar um link placeholder se quiséssemos:
    # final_message = "Perfeito! Pedido confirmado. Você pode acompanhar aqui: [link placeholder]. Excelente aquisição! 🎉"

    logger.info(f"[{node_name}] Generated final confirmation message (simplified).")
    ai_message = AIMessage(content=final_message)

    return {
        "generation": final_message,
        "messages": [ai_message],
        "closing_status": "ORDER_PROCESSED",  # Status final de sucesso
        "error": None,
    }


async def handle_correction_node(
    state: ConversationState, config: dict
) -> Dict[str, Any]:
    """
    Acknowledges the customer's request for correction and prepares for the next step.
    For now, it just acknowledges and ends the turn.
    Sets closing_status back to None or a specific 'CORRECTION_PENDING' status.

    Args:
        state: Requires 'messages', 'correction_details'.
        config: Requires 'llm_fast_instance'.

    Returns:
        Dictionary with 'generation', 'messages', and updated 'closing_status'.
        May also reset 'proposed_solution_details' or parts of it.
    """
    node_name = "handle_correction_node"
    logger.info(f"--- Starting Node: {node_name} (Closing Subgraph) ---")

    messages = state.get("messages", [])
    correction_details = state.get("correction_details")
    llm_fast: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_fast_instance"
    )

    # --- Validations ---
    if not llm_fast:
        return {"error": "Correction handling failed: LLM unavailable."}
    if not messages:
        return {"error": "Correction handling failed: Empty message history."}
    if not correction_details:
        logger.warning(
            f"[{node_name}] No correction details found. Using generic response."
        )
        correction_details = "o detalhe que mencionou"

    logger.debug(f"[{node_name}] Handling correction request: '{correction_details}'")

    # --- Prompt for Acknowledgment ---
    prompt_template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Você é um assistente de vendas lidando com um pedido de correção do cliente durante o fechamento.
O cliente pediu para alterar: **{correction_summary}**.

**Sua Tarefa:**
1.  **Reconheça:** Confirme que você entendeu o pedido de correção (ex: "Entendido!", "Sem problemas.", "Ok, vamos ajustar isso.").
2.  **Indique Próximo Passo (Simples):** Diga que você vai verificar ou ajustar. Por enquanto, não peça mais informações. Ex: "Vou verificar como podemos ajustar o {correction_summary}.", "Deixe-me ajustar o {correction_summary}."
3.  **Seja Conciso e Prestativo:** Mantenha um tom positivo.
4.  **Formatação:** Use formatação WhatsApp sutil. {formatting_instructions}

Gere a mensagem de reconhecimento da correção.""",
            ),
        ]
    )

    parser = StrOutputParser()
    chain = prompt_template | llm_fast | parser

    try:
        acknowledgment_message = await chain.ainvoke(
            {
                "correction_summary": correction_details,
                "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
            }
        )
        acknowledgment_message = acknowledgment_message.strip()

        if not acknowledgment_message:
            raise ValueError("LLM returned empty correction acknowledgment.")

        logger.info(
            f"[{node_name}] Generated correction acknowledgment: '{acknowledgment_message[:100]}...'"
        )
        ai_message = AIMessage(content=acknowledgment_message)

        # O que fazer com o estado?
        # Opção 1: Voltar para um estágio anterior (ex: Presentation) para rediscutir.
        # Opção 2: Manter em Closing, mas com um status específico.
        # Opção 3: Tentar resolver a correção aqui (mais complexo).

        # Por agora, vamos voltar ao estágio de Presentation e limpar o status de closing.
        # Isso força o grafo principal a reavaliar a situação.
        return {
            "generation": acknowledgment_message,
            "messages": [ai_message],
            "closing_status": None,  # Limpa status de closing
            "current_sales_stage": SALES_STAGE_PRESENTATION,  # Volta para apresentação/ajuste
            "proposed_solution_details": None,  # Limpa detalhes propostos para serem redefinidos
            "correction_details": None,  # Limpa detalhes da correção
            "error": None,
        }

    except Exception as e:
        logger.exception(
            f"[{node_name}] Error generating correction acknowledgment: {e}"
        )
        fallback = f"Entendido, vamos verificar a questão sobre {correction_details}."
        ai_message = AIMessage(content=fallback)
        return {
            "generation": fallback,
            "messages": [ai_message],
            "closing_status": None,
            "current_sales_stage": SALES_STAGE_PRESENTATION,
            "proposed_solution_details": None,
            "correction_details": None,
            "error": f"Correction handling failed: {e}",
        }
