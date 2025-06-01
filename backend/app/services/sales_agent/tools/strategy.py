from langchain_core.tools import tool
from typing_extensions import Annotated
from ..agent_state import AgentState
from langgraph.prebuilt import InjectedState
from loguru import logger
from uuid import UUID
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from langchain_core.runnables import RunnableConfig
from app.api.schemas.company_profile import OfferingInfo, CompanyProfileSchema


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
        description="Sugestões de próximos passos dependendo da reação do cliente à tentativa de refutação.",
    )
    # Poderíamos adicionar um campo para "coisas a evitar"
    # things_to_avoid: List[str] = Field(default_factory=list)

    model_config = {"validate_assignment": True}


@tool
async def suggest_objection_response_strategy(
    objection_type: str,
    config: RunnableConfig,
    state: Annotated[AgentState, InjectedState],
    offering_id_str: Optional[str] = None,
    customer_identified_needs: Optional[List[str]] = None,
) -> Dict[
    str, Any
]:  # Retorna um dicionário que pode ser validado com ObjectionResponseStrategy
    """
    Sugere uma estratégia detalhada para responder a uma objeção específica do cliente.
    Analisa o tipo de objeção, o contexto da oferta (se fornecido) e as necessidades
    identificadas do cliente para fornecer táticas de resposta.

    Args:
        objection_type (str): O tipo principal da objeção (ex: 'price', 'need', 'timing', 'trust', 'competitor').
        offering_id_str (Optional[str]): O ID da oferta específica que está sendo discutida e à qual a objeção se refere.
        customer_identified_needs (Optional[List[str]]): Uma lista das necessidades ou dores do cliente já identificadas.
        state (AgentState): [INJETADO AUTOMATICAMENTE, OPCIONAL NESTA TOOL SE OS OUTROS ARGS FOREM SUFICIENTES]
                            O estado completo da conversa, caso a tool precise de mais contexto.
    Returns:
        Dict[str, Any]: Um dicionário contendo sugestões estratégicas estruturadas,
                        aderindo ao schema ObjectionResponseStrategy.
                        Em caso de falha ao gerar estratégia, retorna um dicionário com uma mensagem de erro.
    """
    tool_name = "suggest_objection_response_strategy"
    logger.info(f"--- Executing Tool: {tool_name} ---")
    logger.info(
        f"Objection Type: {objection_type}, Offering Context: {offering_id_str}, Needs: {customer_identified_needs}"
    )

    # --- Lógica Interna da Tool (Pode usar um LLM ou uma base de conhecimento/regras) ---
    # Para este exemplo, vamos simular a lógica com base no objection_type.
    # Em uma implementação real, um LLM seria muito poderoso aqui.
    company_profile = state.company_profile

    try:
        offering_uuid = UUID(offering_id_str)
    except ValueError:
        logger.warning(
            f"[{tool_name}] Invalid UUID format for offering_id_str: '{offering_id_str}'"
        )
        return (
            f"The provided offering ID '{offering_id_str}' is not in a valid format. "
            "An offering ID should be a standard unique identifier."
        )

    offering_in_context: Optional[OfferingInfo] = None
    for offering in company_profile.offering_overview:
        if offering.id == offering_uuid:
            offering_in_context = offering
            break
    llm_primary_instance = config.get("configurable", {}).get("llm_primary_instance")

    # Acessar company_profile e offering_details do estado se necessário e se 'state' for usado
    company_profile: Optional[CompanyProfileSchema] = None
    offering_in_context: Optional[OfferingInfo] = None

    # Construir o prompt para o LLM interno (se usado)
    internal_llm_prompt_parts = [
        f"Você é um especialista em treinamento de vendas. Um cliente levantou uma objeção do tipo '{objection_type}'."
    ]
    if offering_in_context:
        internal_llm_prompt_parts.append(
            f"A objeção é sobre a oferta: '{offering_in_context.name}', que tem as seguintes características: {', '.join(offering_in_context.key_features)} e preço {offering_in_context.price_info}."
        )
    if customer_identified_needs:
        internal_llm_prompt_parts.append(
            f"As necessidades já identificadas do cliente são: {', '.join(customer_identified_needs)}."
        )
    internal_llm_prompt_parts.append(
        "Forneça uma estratégia de resposta detalhada, incluindo: abordagem principal, perguntas sugeridas, pontos chave a enfatizar, "
        "possíveis reenquadramentos e opções de próximos passos. Formate sua resposta como um JSON aderindo ao schema ObjectionResponseStrategy."
    )
    internal_llm_prompt = "\n".join(internal_llm_prompt_parts)
    logger.debug(f"Internal LLM Prompt for objection strategy: {internal_llm_prompt}")

    response_from_internal_llm = await llm_primary_instance.with_structured_output(
        ObjectionResponseStrategy
    ).ainvoke(internal_llm_prompt)
    return response_from_internal_llm.model_dump()
