# backend/app/services/ai_reply/new_agent/components/offer_selector.py

from typing import Dict, List, Optional, Any
from loguru import logger
import json

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

# Schemas
from ..schemas.offer_selection_output import (
    OfferSelectionOutput,
)
from app.api.schemas.company_profile import (
    OfferingInfo,
)  # For type hinting full offering

# State definition
from ..state_definition import RichConversationState, DynamicCustomerProfile

# Helpers from other components (assuming they are accessible)
try:
    from .input_processor import _format_recent_chat_history, _call_structured_llm
except ImportError:
    logger.error(
        "Failed to import helper functions from input_processor for offer_selector. Using fallbacks."
    )

    # Fallbacks to ensure code runs, but functionality will be degraded
    def _format_recent_chat_history(*args, **kwargs) -> str:
        return "Chat history unavailable (fallback)."

    async def _call_structured_llm(*args, **kwargs) -> Optional[Any]:
        logger.error(
            "_call_structured_llm fallback called in offer_selector. This indicates an import error."
        )
        return None


PROMPT_SELECT_OFFER_TEMPLATE_STR = """
Você é um Especialista em Seleção de Produtos IA para a '{company_name}'. Sua tarefa é analisar o contexto da conversa e a lista de OFERTAS DISPONÍVEIS para selecionar a MELHOR OFERTA ÚNICA para o cliente, ou determinar se nenhuma oferta é adequada.

**Contexto da Conversa:**
- Última Mensagem do Cliente: "{last_user_message}"
- Intenção Principal do Cliente (se conhecida): "{last_discerned_intent}"
- Necessidades/Dores Identificadas do Cliente (se houver):
{formatted_identified_needs_pains}
- Histórico Recente da Conversa:
{recent_chat_history}
--- Fim do Histórico ---

**OFERTAS DISPONÍVEIS ATUALMENTE (Nome, Descrição Resumida, Características Principais, Preço):**
{available_offerings_formatted_list}
--- Fim das Ofertas Disponíveis ---

**Sua Tarefa (Preencha o JSON `OfferSelectionOutput`):**

1.  **Análise e Seleção:**
    *   Com base no contexto da conversa e nas necessidades do cliente, avalie CADA OFERTA DISPONÍVEL.
    *   Selecione a **MELHOR OFERTA ÚNICA** que mais se adequa.
    *   Se múltiplas ofertas parecerem boas, escolha aquela que resolve a necessidade mais premente ou recentemente discutida.
    *   Se nenhuma oferta for um bom ajuste, indique isso claramente.

2.  **Preenchimento do `OfferSelectionOutput`:**

    *   **`selected_offer` (Objeto `SelectedOffer`):**
        *   Se uma oferta for selecionada:
            *   `product_name`: O nome EXATO da oferta selecionada da lista de OFERTAS DISPONÍVEIS.
            *   `reason_for_selection`: Sua justificativa concisa para escolher esta oferta.
            *   `confidence_score`: Sua confiança (0.0 a 1.0) de que esta é a melhor escolha.
            *   `key_benefit_to_highlight`: O principal benefício desta oferta que o agente deve destacar para o cliente, com base na conversa.
        *   Se NENHUMA oferta for adequada, deixe `selected_offer` como `null`.

    *   **`no_suitable_offer_found` (Boolean):**
        *   `true` se você determinar que NENHUMA das ofertas disponíveis é um bom ajuste para o cliente.
        *   `false` caso contrário (mesmo que a confiança seja baixa, mas uma seleção foi feita).

    *   **`alternative_suggestions_if_no_match` (Lista de Strings):**
        *   Se `no_suitable_offer_found` for `true`, sugira brevemente 1-2 produtos relacionados (se houver algum minimamente próximo) ou tópicos que o agente poderia explorar.
        *   Ex: ["Podemos verificar se o Produto Y, que é similar, te atenderia?", "Talvez possamos focar em entender melhor sua necessidade X."]

    *   **`clarifying_questions_to_ask` (Lista de Strings):**
        *   Se o contexto da conversa for muito vago para fazer uma boa seleção, liste 1-2 perguntas que o agente poderia fazer para obter mais clareza.
        *   Ex: ["Para qual finalidade principal você usaria este tipo de solução?", "Você tem alguma preferência de característica X ou Y?"]
        *   Preencha isto PRINCIPALMENTE se `selected_offer` for `null` devido à vagueza.

    *   **`overall_justification` (String):**
        *   Sua justificativa geral para a decisão (seja uma seleção, nenhuma oferta encontrada, ou necessidade de clarificação).

**Instruções Cruciais:**
*   **FOCO NA DISPONIBILIDADE:** Selecione APENAS entre as "OFERTAS DISPONÍVEIS ATUALMENTE". Não invente ou sugira ofertas não listadas.
*   **UMA ÚNICA MELHOR OFERTA:** Se for selecionar, selecione apenas UMA.
*   **SEJA DECISIVO:** Se a confiança for muito baixa (< 0.4), é melhor definir `no_suitable_offer_found: true`.
*   Responda APENAS com o objeto JSON formatado de acordo com o schema `OfferSelectionOutput`.

Linguagem para justificativas e sugestões: {language}
Tom para justificativas e sugestões: {sales_tone}
"""


def _format_identified_needs_pains_for_prompt(profile: DynamicCustomerProfile) -> str:
    """
    Formats identified needs and pain points for the LLM prompt.

    Args:
        profile: The dynamic customer profile.

    Returns:
        A formatted string of needs and pain points.
    """
    lines = []
    if profile.get("identified_needs"):
        lines.append("  Necessidades:")
        for need in profile["identified_needs"]:
            if need.get("status") != "addressed_by_agent":  # Focus on active/confirmed
                lines.append(f"    - {need.get('text')} (Status: {need.get('status')})")
    if profile.get("identified_pain_points"):
        lines.append("  Dores/Problemas:")
        for pain in profile["identified_pain_points"]:
            if pain.get("status") != "addressed_by_agent":
                lines.append(f"    - {pain.get('text')} (Status: {pain.get('status')})")

    return (
        "\n".join(lines)
        if lines
        else "Nenhuma necessidade ou dor específica identificada ainda."
    )


def _format_available_offerings_for_prompt(offerings: List[OfferingInfo]) -> str:
    """
    Formats the list of available company offerings for the LLM prompt.

    Args:
        offerings: A list of OfferingInfo objects from the company profile.

    Returns:
        A string listing available offerings with key details.
    """
    if not offerings:
        return "Nenhuma oferta disponível no momento."

    formatted_list = []
    for offer in offerings:
        # Ensure all parts are strings before joining
        offer = OfferingInfo.model_validate(offer)
        name = offer.name or "Nome não disponível"
        desc = offer.short_description or "Descrição não disponível"
        features_list = offer.key_features or []
        features_str = (
            ", ".join(features_list) if features_list else "Não especificadas"
        )
        price = offer.price_info or "Preço sob consulta"

        formatted_list.append(
            f"- Nome: {name}\n"
            f"  Descrição: {desc}\n"
            f"  Características Principais: {features_str}\n"
            f"  Preço: {price}"
        )
    return "\n".join(formatted_list)


async def select_offer_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Uses an LLM to select the best available offer based on user needs and conversation context.

    Args:
        state: The current conversation state.
        config: The graph configuration, expected to contain 'llm_primary_instance'
                or 'llm_strategy_instance'.

    Returns:
        A dictionary with 'offer_selection_result' containing the OfferSelectionOutput
        or None, and 'last_processing_error' if an error occurred.
    """
    node_name = "select_offer_node"
    logger.info(
        f"--- Starting Node: {node_name} (Turn: {state.get('current_turn_number', 0)}) ---"
    )

    llm: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_strategy_instance"
    ) or config.get("configurable", {}).get("llm_primary_instance")

    if not llm:
        logger.error(f"[{node_name}] LLM instance not found in config. Cannot proceed.")
        return {
            "offer_selection_result": None,
            "last_processing_error": "LLM for offer selection unavailable.",
        }
    if not callable(_call_structured_llm):
        logger.error(
            f"[{node_name}] _call_structured_llm is not callable. Critical import error."
        )
        return {
            "offer_selection_result": None,
            "last_processing_error": "Helper function _call_structured_llm unavailable.",
        }

    company_profile_dict = state.get("company_profile", {})
    company_name = company_profile_dict.get("company_name", "nossa empresa")
    language = company_profile_dict.get("language", "pt-br")
    sales_tone = company_profile_dict.get("sales_tone", "amigável e prestativo")

    available_offerings: List[OfferingInfo] = company_profile_dict.get(
        "offering_overview", []
    )
    if not available_offerings:
        logger.warning(
            f"[{node_name}] No offerings found in company_profile. LLM cannot select an offer."
        )
        # Return a specific "no offer available" output directly
        no_offer_output = OfferSelectionOutput(
            selected_offer=None,
            no_suitable_offer_found=True,
            alternative_suggestions_if_no_match=[
                "Nenhuma oferta cadastrada no momento."
            ],
            clarifying_questions_to_ask=[],
            overall_justification="Não há ofertas configuradas no perfil da empresa para seleção.",
        )
        return {
            "offer_selection_result": no_offer_output.model_dump(),
            "last_processing_error": None,  # Not an error, but a state
        }

    available_offerings_formatted = _format_available_offerings_for_prompt(
        available_offerings
    )

    customer_profile_dynamic: DynamicCustomerProfile = state.get("customer_profile_dynamic", {})  # type: ignore
    formatted_needs_pains = _format_identified_needs_pains_for_prompt(
        customer_profile_dynamic
    )

    recent_chat_history = _format_recent_chat_history(state.get("messages", []))
    last_user_message = state.get(
        "current_user_input_text", "N/A (sem mensagem do usuário neste turno)"
    )
    last_discerned_intent = customer_profile_dynamic.get(
        "last_discerned_intent", "Não identificado"
    )

    prompt_values = {
        "company_name": company_name,
        "language": language,
        "sales_tone": sales_tone,
        "last_user_message": last_user_message,
        "last_discerned_intent": last_discerned_intent,
        "formatted_identified_needs_pains": formatted_needs_pains,
        "recent_chat_history": recent_chat_history,
        "available_offerings_formatted_list": available_offerings_formatted,
    }

    logger.debug(f"[{node_name}] Invoking LLM for offer selection.")
    # logger.trace(f"[{node_name}] Prompt values for offer selection: {json.dumps(prompt_values, indent=2, default=str)}")

    selection_output_obj: Optional[OfferSelectionOutput] = await _call_structured_llm(
        llm=llm,
        prompt_template_str=PROMPT_SELECT_OFFER_TEMPLATE_STR,  # Use the template string
        prompt_values=prompt_values,
        output_schema=OfferSelectionOutput,
        node_name_for_logging=node_name,
    )

    if not selection_output_obj:
        logger.error(
            f"[{node_name}] Failed to get structured output from LLM for offer selection."
        )
        # Fallback: indicate no offer could be selected due to system error
        error_output = OfferSelectionOutput(
            selected_offer=None,
            no_suitable_offer_found=True,  # Treat as no offer found
            alternative_suggestions_if_no_match=[],
            clarifying_questions_to_ask=[],
            overall_justification="Erro interno ao tentar selecionar uma oferta.",
        )
        return {
            "offer_selection_result": error_output.model_dump(),
            "last_processing_error": "Offer selection LLM call failed or returned invalid structure.",
        }

    logger.info(f"[{node_name}] Offer selection process completed.")
    if selection_output_obj.selected_offer:
        logger.info(
            f"  Selected Offer: {selection_output_obj.selected_offer.product_name}"
        )
        logger.info(
            f"  Reason: {selection_output_obj.selected_offer.reason_for_selection}"
        )
        logger.info(
            f"  Benefit to Highlight: {selection_output_obj.selected_offer.key_benefit_to_highlight}"
        )
    elif selection_output_obj.no_suitable_offer_found:
        logger.info("  No suitable offer found by LLM.")
        if selection_output_obj.alternative_suggestions_if_no_match:
            logger.info(
                f"  Alternative suggestions: {selection_output_obj.alternative_suggestions_if_no_match}"
            )
    if selection_output_obj.clarifying_questions_to_ask:
        logger.info(
            f"  Clarifying questions to ask: {selection_output_obj.clarifying_questions_to_ask}"
        )

    logger.debug(
        f"  Overall Justification: {selection_output_obj.overall_justification}"
    )

    return {
        "offer_selection_result": selection_output_obj.model_dump(),  # Store as dict
        "last_processing_error": None,
    }
