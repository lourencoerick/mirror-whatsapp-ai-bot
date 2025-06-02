from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from typing_extensions import Annotated
from ..agent_state import AgentState  # Assuming AgentState is in a parent directory
from langgraph.types import Command
from langgraph.prebuilt import InjectedState
from loguru import logger
from uuid import UUID
from pydantic import (
    BaseModel,
    Field,
)  # Use Field alias for clarity if needed
from typing import List, Optional, Dict, Any
from langchain_core.runnables import RunnableConfig
from app.api.schemas.company_profile import (
    OfferingInfo,
    CompanyProfileSchema,
)  # Ensure these are correct paths


class ObjectionResponseStrategy(BaseModel):
    """
    Estrutura para as sugestões de estratégia de resposta a objeções.
    """

    primary_approach: str = Field(
        description="A abordagem principal ou filosofia para lidar com este tipo de objeção (ex: 'Reenquadrar valor vs. custo', 'Aprofundar na necessidade não percebida')."
    )
    suggested_questions_to_ask: List[str] = Field(
        default_factory=list,
        description="Perguntas específicas que o agente pode fazer ao cliente para entender melhor a objeção ou redirecionar a conversa.",
    )
    key_points_to_emphasize: List[str] = Field(
        default_factory=list,
        description="Benefícios, características ou pontos de valor específicos da oferta ou da empresa que devem ser reforçados.",
    )
    potential_reframes_or_analogies: List[str] = Field(
        default_factory=list,
        description="Maneiras de recontextualizar a objeção ou analogias que podem ajudar o cliente a ver de outra perspectiva.",
    )
    next_step_options: List[str] = Field(
        default_factory=list,
        description="Sugestões de próximos passos CONCRETOS E REALIZÁVEIS pelo agente de vendas virtual, considerando as capacidades da empresa. Evite sugerir ações que a empresa não oferece (ex: demonstrações, se não disponíveis).",
    )
    model_config = {"validate_assignment": True}


@tool
async def suggest_objection_response_strategy(
    objection_type: str,
    config: RunnableConfig,  # Contains llm_primary_instance, db_session_factory etc.
    state: Annotated[AgentState, InjectedState],  # Access to full agent state
    tool_call_id: Annotated[str, InjectedToolCallId],
    offering_id_str: Optional[str] = None,
    customer_identified_needs: Optional[List[str]] = None,
    conversation_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Provides strategic advice for handling customer objections.
    The output is structured suggestions FOR THE AI AGENT to consider.
    The AI agent should NOT directly output this structure to the user, but rather
    synthesize the information into a natural, conversational response,
    filtering suggestions based on actual company offerings.

    Args:
        objection_type: Main type of objection (e.g., 'price', 'need').
        config: RunnableConfig containing 'llm_primary_instance'.
        state: Current agent state, providing access to company_profile.
        offering_id_str: ID of the specific offering being discussed.
        customer_identified_needs: List of customer's identified needs.
        conversation_context: Brief context of the objection.

    Returns:
        A dictionary adhering to ObjectionResponseStrategy schema, or an error dict.
    """
    tool_name = "suggest_objection_response_strategy"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(
        f"Objection Type: {objection_type}, Offering ID: {offering_id_str}, Needs: {customer_identified_needs}"
    )

    llm_for_strategy: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )
    if not llm_for_strategy:
        logger.error(f"[{tool_name}] LLM for strategy generation not found in config.")
        return {
            "error": "Internal configuration error: LLM for strategy not available."
        }

    # Access company_profile from the injected state
    company_profile: Optional[CompanyProfileSchema] = state.company_profile
    if not company_profile:
        logger.warning(
            f"[{tool_name}] Company profile not found in agent state. Strategy suggestions might be generic."
        )
        # Proceed with generic advice, or return an error/specific message
        # For now, let's allow it to proceed but the prompt will be less informed.

    offering_in_context: Optional[OfferingInfo] = None
    if offering_id_str and company_profile and company_profile.offering_overview:
        try:
            offering_uuid = UUID(offering_id_str)
            for offering in company_profile.offering_overview:
                if offering.id == offering_uuid:
                    offering_in_context = offering
                    break
        except ValueError:
            logger.warning(
                f"[{tool_name}] Invalid UUID format for offering_id_str: '{offering_id_str}'"
            )
            # Continue without specific offering context if ID is bad

    # --- Constructing the prompt for the internal LLM ---
    internal_llm_prompt_parts = [
        f"Você é um especialista sênior em treinamento de vendas. Sua tarefa é gerar uma estratégia detalhada para um assistente de vendas virtual (IA) lidar com uma objeção de cliente.",
        f"O assistente de vendas representa a empresa '{company_profile.company_name if company_profile else 'N/A'}'.",
        f"O tipo de objeção levantada pelo cliente é: '{objection_type}'.",
    ]

    if conversation_context:
        internal_llm_prompt_parts.append(
            f"Contexto da conversa em que a objeção surgiu: '{conversation_context}'."
        )
    if offering_in_context:
        internal_llm_prompt_parts.append(
            f"A objeção refere-se à oferta: '{offering_in_context.name}'. Detalhes da oferta: Descrição='{offering_in_context.short_description}', Preço='{offering_in_context.price_info or offering_in_context.price}'."
        )
    if customer_identified_needs:
        internal_llm_prompt_parts.append(
            f"Necessidades do cliente já identificadas: {', '.join(customer_identified_needs)}."
        )

    # --- NEW: Adding Company Capabilities to the Internal LLM Prompt ---
    if company_profile:
        internal_llm_prompt_parts.append(
            "\nInformações sobre as capacidades da empresa para guiar suas sugestões de 'next_step_options':"
        )
        # Example: Explicitly state what's available. You'll need to define these in CompanyProfileSchema
        # or derive them. For now, let's use fallback_contact_info as an example of a concrete next step.
        if company_profile.fallback_contact_info:
            internal_llm_prompt_parts.append(
                f"- A empresa PODE direcionar o cliente para o seguinte contato para questões complexas ou negociações: '{company_profile.fallback_contact_info}'."
            )
        else:
            internal_llm_prompt_parts.append(
                "- A empresa NÃO possui um canal de fallback específico listado para negociações complexas (o agente deve tentar resolver ou pedir para o cliente aguardar)."
            )

        # Add more based on your CompanyProfileSchema. For example:
        # if getattr(company_profile, "offers_demos", False):
        #     internal_llm_prompt_parts.append("- A empresa OFERECE demonstrações de produtos.")
        # else:
        #     internal_llm_prompt_parts.append("- A empresa NÃO oferece demonstrações de produtos como um próximo passo padrão.")

        # if getattr(company_profile, "has_testimonials_publicly_available", False): # Example field
        #     internal_llm_prompt_parts.append("- A empresa POSSUI depoimentos que podem ser mencionados.")
        # else:
        #     internal_llm_prompt_parts.append("- A empresa NÃO possui depoimentos facilmente acessíveis para o agente compartilhar.")

        internal_llm_prompt_parts.append(
            "Ao sugerir 'next_step_options', foque em ações que o assistente virtual PODE REALMENTE EXECUTAR ou que são consistentes com as práticas da empresa mencionadas acima. "
            "Priorize próximos passos como: fornecer mais informações, esclarecer dúvidas sobre o produto/oferta em questão, discutir opções de pagamento (se conhecidas), ou, como último recurso, usar o contato de fallback."
        )
    else:
        internal_llm_prompt_parts.append(
            "\nAVISO: O perfil da empresa não está disponível. Suas sugestões de 'next_step_options' devem ser mais genéricas, e o agente de vendas principal precisará filtrá-las."
        )

    internal_llm_prompt_parts.append(
        "\nForneça uma estratégia de resposta detalhada, incluindo: 'primary_approach', 'suggested_questions_to_ask', 'key_points_to_emphasize', "
        "'potential_reframes_or_analogies', e 'next_step_options'. "
        "Formate sua resposta como um JSON que adira estritamente ao schema ObjectionResponseStrategy."
    )
    internal_llm_prompt_str = "\n".join(internal_llm_prompt_parts)
    logger.debug(
        f"Internal LLM Prompt for objection strategy:\n{internal_llm_prompt_str}"
    )

    tool_message_content: str
    try:
        structured_llm_chain = llm_for_strategy.with_structured_output(
            ObjectionResponseStrategy
        )
        response_model: ObjectionResponseStrategy = await structured_llm_chain.ainvoke(
            internal_llm_prompt_str
        )

        strategy_json_str = response_model.model_dump_json(indent=2)

        # --- Append the guidance for the main agent to the ToolMessage content ---
        guidance_for_main_agent = (
            "\n\n--- INSTRUÇÃO PARA O AGENTE DE VENDAS (IA) ---:\n"
            "Analise a estratégia JSON acima. NÃO a apresente diretamente ao usuário.\n"
            "Em vez disso, use-a como base para formular sua PRÓPRIA resposta conversacional e natural.\n"
            "Ao considerar os 'next_step_options' sugeridos, priorize e selecione APENAS aqueles que são REALMENTE POSSÍVEIS de serem executados pela empresa ou por você (IA), com base no perfil da empresa e nas ferramentas disponíveis. "
        )
        tool_message_content = strategy_json_str + guidance_for_main_agent
        logger.success(
            f"[{tool_name}] Successfully generated objection response strategy."
        )

    except Exception as e:
        logger.exception(
            f"[{tool_name}] Error calling internal LLM or processing strategy: {e}"
        )
        tool_message_content = f'{{"error": "Failed to generate objection strategy: {str(e)}"}}\n\n--- INSTRUÇÃO PARA O AGENTE DE VENDAS (IA) ---:\nOcorreu um erro ao gerar a estratégia. Tente lidar com a objeção usando seu conhecimento geral e as informações do perfil da empresa.'

    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=tool_message_content,
                    name=tool_name,
                    tool_call_id=tool_call_id,
                )
            ]
        }
    )
