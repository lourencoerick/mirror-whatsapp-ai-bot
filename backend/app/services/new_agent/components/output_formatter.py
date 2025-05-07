# app/services/ai_reply/new_agent/components/output_formatter.py
from typing import Dict, Any
from loguru import logger

from ..state_definition import RichConversationState

# Importar função de formatação se existir, senão fazer aqui
# from ..prompt_utils import format_whatsapp_markdown


def _apply_whatsapp_formatting(text: str) -> str:
    """Aplica formatação básica (placeholder)."""
    # TODO: Implementar a lógica real de formatação se necessário,
    # ou apenas retornar o texto se o LLM já formata bem.
    # Exemplo simples: apenas garantir que não haja espaços extras.
    if not text:
        return ""
    return text.strip()


async def output_formatter_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """Formata a saída final do agente."""
    node_name = "output_formatter_node"
    logger.info(f"--- Starting Node: {node_name} ---")

    generated_text = state.get("last_agent_generation_text")

    if not generated_text:
        logger.warning(
            f"[{node_name}] No text found in 'last_agent_generation_text' to format."
        )
        return {
            "final_agent_message_text": ""
        }  # Retorna vazio se não há o que formatar

    formatted_text = _apply_whatsapp_formatting(generated_text)
    logger.debug(f"[{node_name}] Formatted text: '{formatted_text[:100]}...'")

    return {"final_agent_message_text": formatted_text}
