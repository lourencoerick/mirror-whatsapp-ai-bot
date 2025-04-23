import json
from typing import List, Optional, Tuple, Dict, Any

from loguru import logger
from pydantic import ValidationError

from langchain_openai import ChatOpenAI
from trustcall import create_extractor

from app.simulation.schemas.persona_definition import PersonaDefinition, InfoRequest
from app.simulation.schemas.persona_state import PersonaState, ExtractedFact
from app.models.simulation.simulation import SimulationOutcomeEnum

try:
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
    fact_extractor: Optional[Any] = create_extractor(
        llm,
        tools=[ExtractedFact],
        tool_choice="ExtractedFact",
        enable_inserts=True,
    )
    logger.info("Trustcall extractor for ExtractedFact initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize LLM or Trustcall extractor: {e}")
    fact_extractor = None

# --- Main Logic ---


async def get_next_persona_action(
    persona: PersonaDefinition, ai_response_text: str, current_state: PersonaState
) -> Tuple[Optional[str], PersonaState, bool, Optional[SimulationOutcomeEnum]]:
    """
    Determines the persona's next action by using trustcall to extract facts
    from the AI response and update the persona's knowledge state.

    Args:
        persona: The definition of the current persona.
        ai_response_text: The last response from the AI Seller.
        current_state: The current PersonaState object.

    Returns:
        A tuple containing:
            - next_persona_message (str or None if terminating)
            - updated_state (PersonaState object)
            - terminate_simulation (bool)
            - termination_outcome (Optional[SimulationOutcomeEnum])
    """
    logger.debug(
        f"Persona '{persona.persona_id}' current facts: {current_state.extracted_facts}"
    )
    logger.debug(f"Processing AI response: '{ai_response_text}'")

    if not fact_extractor:
        logger.error("Fact extractor unavailable. Cannot proceed.")
        return None, current_state, True, SimulationOutcomeEnum.SIMULATION_ERROR

    updated_state = current_state.model_copy(deep=True)
    terminate = False
    outcome = None
    next_persona_message = None

    if ai_response_text:
        # 1. Prepare prompt to extract facts
        needed_info_str = ", ".join(
            [
                f"'{req.attribute}' for '{req.entity}'"
                for req in persona.information_needed
                if not updated_state.has_fact(req.entity, req.attribute)
            ]
        )
        prompt = f"""
        Analyze the AI Seller's response below. The customer still needs: [{needed_info_str}].
        Extract each distinct fact as an 'ExtractedFact' JSON object with keys 'entity', 'attribute', and 'value'.
        If a requested entity is clearly unavailable, set 'availability' to 'Not available'.

        AI Seller Response:
        ---
        {ai_response_text}
        ---

        Return facts as 'ExtractedFact' objects:
        """
        try:
            logger.debug("Calling fact extractor...")
            trustcall_input = {"messages": [{"role": "user", "content": prompt}]}
            trustcall_result = await fact_extractor.ainvoke(trustcall_input)

            # 2. Process extracted facts
            if trustcall_result and trustcall_result.get("responses"):
                newly_extracted_facts = trustcall_result["responses"]
                logger.info(f"Extracted {len(newly_extracted_facts)} facts.")
                current_facts = {
                    (f.entity, f.attribute) for f in updated_state.extracted_facts
                }
                added = 0
                for fact in newly_extracted_facts:
                    if (
                        isinstance(fact, ExtractedFact)
                        and (fact.entity, fact.attribute) not in current_facts
                    ):
                        updated_state.extracted_facts.append(fact)
                        current_facts.add((fact.entity, fact.attribute))
                        added += 1
                        logger.debug(f"Added fact: {fact.model_dump()}")
                if added:
                    logger.info(f"Added {added} new facts.")
            else:
                logger.warning("No facts returned by extractor.")
        except Exception as e:
            logger.exception(f"Error during fact extraction: {e}")
            logger.error("Proceeding with previous state due to extractor error.")

    # 3. Check which information is still needed
    still_needed: List[InfoRequest] = []
    for req in persona.information_needed:
        if not updated_state.has_fact(req.entity, req.attribute):
            still_needed.append(req)

    # 4. Check success criteria
    if not still_needed and "state:all_info_extracted" in persona.success_criteria:
        logger.info("All required information obtained.")
        terminate = True
        outcome = SimulationOutcomeEnum.INFO_OBTAINED

    # 5. Determine next question if not terminating
    elif not terminate and still_needed:
        missing = still_needed[0]
        template = persona.info_attribute_to_question_template.get(missing.attribute)
        if template:
            try:
                next_persona_message = template.format(entity=missing.entity)
            except KeyError:
                logger.error(
                    f"Template missing '{{entity}}' for '{missing.attribute}'."
                )
                next_persona_message = f"Can you tell me about '{missing.attribute}' for '{missing.entity}'?"
        else:
            next_persona_message = (
                f"Can you tell me about '{missing.attribute}' for '{missing.entity}'?"
            )
        logger.debug(f"Next persona message: '{next_persona_message}'")

    # 6. Return the determined action
    return next_persona_message, updated_state, terminate, outcome
