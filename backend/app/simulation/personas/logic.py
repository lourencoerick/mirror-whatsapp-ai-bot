# backend/app/simulation/personas/logic.py

import json
from typing import List, Optional, Tuple, Dict, Any

from loguru import logger
from pydantic import BaseModel  # Para o estado interno

# Importar o cliente LLM e trustcall
# Usaremos OpenAI como exemplo, ajuste se usar outro
from langchain_openai import ChatOpenAI
from trustcall import create_extractor, ToolExtractor  # Importar ToolExtractor

# Importar Schemas e Enums
from app.simulation.schemas.persona_definition import PersonaDefinition
from app.simulation.schemas.persona_state import PersonaState  # O schema que criamos
from app.models.simulation.simulation import SimulationOutcomeEnum

# --- Configuração do LLM e Trustcall ---

# Inicializa o cliente LLM (ajuste o modelo conforme necessário)
# Certifique-se que a API Key (e.g., OPENAI_API_KEY) está nas variáveis de ambiente
try:
    # Usando um modelo mais recente e capaz para extração/patch
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

    # Cria o extrator do trustcall configurado para o nosso PersonaState
    # Usaremos 'any' tool_choice pois só temos uma ferramenta (o schema PersonaState)
    # enable_inserts=False pois queremos apenas ATUALIZAR o estado existente
    persona_state_extractor: ToolExtractor = create_extractor(
        llm,
        tools=[PersonaState],
        tool_choice="PersonaState",  # Força o uso do nosso schema
        enable_inserts=False,  # Importante: Apenas atualiza, não cria novo
    )
    logger.info("Trustcall extractor for PersonaState initialized successfully.")

except Exception as e:
    logger.error(f"Failed to initialize LLM or Trustcall extractor: {e}")
    # Tratar erro - talvez levantar exceção para parar o simulador?
    persona_state_extractor = None  # Define como None para checagem posterior

# --- Lógica Principal ---


async def get_next_persona_action(
    persona: PersonaDefinition, ai_response_text: str, current_state: PersonaState
) -> Tuple[Optional[str], PersonaState, bool, Optional[SimulationOutcomeEnum]]:
    """
    Determines the persona's next action by using trustcall to update
    the persona's knowledge state based on the AI response.

    Args:
        persona: The definition of the current persona.
        ai_response_text: The last response from the AI Seller.
        current_state: The current PersonaState object representing what the
                       persona knows.

    Returns:
        A tuple containing:
            - next_persona_message (str or None if terminating)
            - updated_state (PersonaState object)
            - terminate_simulation (bool)
            - termination_outcome (Optional[SimulationOutcomeEnum])
    """
    logger.debug(
        f"Persona '{persona.persona_id}' current state: {current_state.model_dump(exclude_none=True)}"
    )
    logger.debug(f"Processing AI response: '{ai_response_text}'")

    if not persona_state_extractor:
        logger.error("Trustcall extractor is not available. Cannot proceed.")
        # Retorna estado inalterado e erro
        return None, current_state, True, SimulationOutcomeEnum.SIMULATION_ERROR

    updated_state = current_state  # Começa com o estado atual
    terminate = False
    outcome = None
    next_persona_message = None

    if ai_response_text:  # Só tenta atualizar se houver resposta da IA
        # 1. Preparar chamada para trustcall para ATUALIZAR o estado
        prompt = f"""
        Update the persona's knowledge state (JSON object below) based ONLY on the information provided in the AI Seller's response.
        Generate JSON Patch operations to add or modify fields in the existing state for information explicitly mentioned by the seller.
        Do not remove existing information unless directly contradicted by the new response.
        Focus on filling fields that are currently null or providing more specific details if available.

        Existing Persona State:
        {current_state.model_dump_json(indent=2)}

        AI Seller Response:
        ---
        {ai_response_text}
        ---

        Generate JSON Patch operations to update the 'PersonaState':
        """

        try:
            logger.debug("Calling trustcall extractor to update persona state...")
            # Formato esperado pelo invoke com 'existing'
            trustcall_input = {
                "messages": [{"role": "user", "content": prompt}],
                "existing": {
                    "PersonaState": current_state.model_dump()
                },  # Passa o estado atual
            }
            trustcall_result = await persona_state_extractor.ainvoke(trustcall_input)

            # 2. Processar resultado do trustcall
            if trustcall_result and trustcall_result.get("responses"):
                # trustcall retorna uma lista de respostas, pegamos a primeira (pois só pedimos PersonaState)
                updated_state_data = trustcall_result["responses"][0]
                if isinstance(updated_state_data, PersonaState):
                    updated_state = updated_state_data  # Já vem validado!
                    logger.info(
                        f"Persona state updated by trustcall: {updated_state.model_dump(exclude_none=True)}"
                    )
                else:
                    # Se não for PersonaState, pode ser um erro ou formato inesperado
                    logger.warning(
                        f"Trustcall returned unexpected response type: {type(updated_state_data)}. State not updated."
                    )
            else:
                logger.warning(
                    "Trustcall did not return a valid response. State not updated."
                )
                # Considerar se isso deve ser um erro fatal para a simulação

        except Exception as e:
            logger.exception(f"Error invoking trustcall extractor: {e}")
            # Decide se continua com o estado antigo ou termina com erro
            # Por enquanto, continua com estado antigo, mas loga o erro
            logger.error(
                "Proceeding with previous persona state due to trustcall error."
            )

    # 3. Verificar informações restantes e critério de sucesso
    still_needed = [
        info_key
        for info_key in persona.information_needed
        if getattr(updated_state, info_key, None)
        is None  # Checa se o campo correspondente no estado é None
    ]
    logger.debug(f"Info still needed after update: {still_needed}")

    if not still_needed and "state:info_needed_empty" in persona.success_criteria:
        logger.info(
            f"Persona '{persona.persona_id}' obtained all required information. Success criterion met."
        )
        terminate = True
        # Mapear para outcome de sucesso apropriado (pode precisar de mais lógica)
        outcome = (
            SimulationOutcomeEnum.INFO_OBTAINED
        )  # Ou SALE_COMPLETED/LEAD_QUALIFIED

    # 4. Determinar próxima pergunta (se não for terminar)
    if not terminate and still_needed:
        next_info_key = still_needed[0]
        next_persona_message = persona.info_to_question_map.get(next_info_key)
        if not next_persona_message:
            logger.warning(
                f"No question defined for key: '{next_info_key}'. Using generic follow-up."
            )
            next_persona_message = f"Ok, entendi. E sobre '{next_info_key}'?"
    elif not terminate and not still_needed:
        # Caso estranho: toda info obtida, mas critério de sucesso não foi 'state:info_needed_empty'
        logger.warning(
            "All info obtained, but success criteria not met? Ending simulation as INFO_OBTAINED."
        )
        terminate = True
        outcome = SimulationOutcomeEnum.INFO_OBTAINED

    # 5. Retornar a ação
    return next_persona_message, updated_state, terminate, outcome
