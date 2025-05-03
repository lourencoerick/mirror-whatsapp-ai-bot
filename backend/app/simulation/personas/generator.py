# backend/app/simulation/personas/generator.py

import json
import uuid
import random
from typing import Optional, List, Any, Dict

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_openai import ChatOpenAI
from trustcall import create_extractor

from app.simulation.schemas import persona as persona_schemas
from app.api.schemas.company_profile import CompanyProfileSchema
from app.simulation.repositories import persona as persona_repo


from app.api.schemas.contact import ContactCreate
from app.services.repository import (
    contact as contact_repo,
)
from app.services.repository import (
    conversation as converastion_repo,
)

from app.models.conversation import ConversationStatusEnum
from app.models.contact import Contact
from app.models.account import Account

# --- LLM and Trustcall setup ---
try:
    llm_generator = ChatOpenAI(model="gpt-4o", temperature=0.7)
    persona_generator_extractor: Optional[Any] = create_extractor(
        llm_generator,
        tools=[persona_schemas.PersonaBase],
        tool_choice="PersonaBase",
        enable_inserts=True,
    )
    logger.info("Trustcall extractor for PersonaBase generation initialized.")
except Exception as e:
    logger.error(f"Failed to initialize LLM or Trustcall extractor for generation: {e}")
    persona_generator_extractor = None


# --- Prompt ---
GENERATOR_SYSTEM_PROMPT_PT = """
SYSTEM: Você é um especialista em marketing e vendas B2C, encarregado de criar perfis de personas de clientes realistas para simular interações de vendas via WhatsApp. Seu objetivo é gerar UMA definição de persona em formato JSON que será usada para testar um assistente de vendas de IA.

TASK: Com base no perfil da empresa fornecido abaixo e no **tipo de persona desejado**, gere UM objeto JSON contendo os campos para uma persona de cliente (`persona_id`, `simulation_contact_identifier`, `description`, `initial_message`, `objective`, `information_needed`, `info_attribute_to_question_template`, `success_criteria`, `failure_criteria`). A persona deve ser relevante para o público-alvo e as ofertas da empresa. O `simulation_contact_identifier` deve ser plausível (formato '55[DDD][9 dígitos]').

**TIPO DE PERSONA DESEJADO: {persona_type_description}**

REGRAS PARA GERAÇÃO DOS DADOS DA PERSONA:
1.  **Relevância:** A persona (descrição, mensagem inicial, objetivo) deve ser plausível e diretamente relacionada ao negócio descrito no perfil da empresa. Considere o `target_audience` e o `offering_overview`. Crie personas variadas.
2.  **`persona_id`:** Crie um ID descritivo em formato snake_case (e.g., 'cliente_curioso_bolo', 'comprador_rapido_pao'). Deve ser único.
3.  **`description`:** Escreva uma descrição concisa (1 frase).
4.  **`initial_message`:** Crie uma primeira mensagem natural e curta.
5.  **`objective`:** Defina um objetivo claro e específico.
6.  **`information_needed`:** Liste os fatos específicos (objetos com 'entity' e 'attribute') que a persona precisa.
7.  **`info_attribute_to_question_template`:** Para CADA atributo *único* em `information_needed`, crie uma entrada neste dicionário (template de pergunta com `{{entity}}` se aplicável).
8.  **Critérios:** Use `success_criteria` (e.g., `["state:all_info_extracted"]`) e `failure_criteria` (e.g., `["event:ai_fallback_detected", "turn_count > 8"]`).

PERFIL DA EMPRESA (CONTEXTO):
```json
{company_profile_json}
```
INSTRUÇÃO FINAL: Gere APENAS o objeto JSON contendo os campos da persona conforme as regras acima. Não inclua nenhum outro texto ou explicação.
"""


# --- Modular Functions ---
async def generate_persona_data(
    profile: CompanyProfileSchema,
    persona_type_description: str,
) -> Optional[persona_schemas.PersonaBase]:
    """
    Generates persona base data using the LLM based on company profile.
    Args:
        profile: The CompanyProfileSchema object for context.
        persona_type_description: Description of the desired persona type.

    Returns:
        A validated PersonaBase Pydantic schema object, or None if generation fails.
    """
    if not persona_generator_extractor:
        logger.error("Persona generator extractor not available.")
        return None

    logger.debug(f"Generating persona data for type: {persona_type_description}")
    try:
        profile_json_str = profile.model_dump_json(indent=2)
        prompt = GENERATOR_SYSTEM_PROMPT_PT.format(
            company_profile_json=profile_json_str,
            persona_type_description=persona_type_description,
        )
        trustcall_input = {"messages": [{"role": "system", "content": prompt}]}

        logger.debug("Calling trustcall persona generator extractor...")
        trustcall_result = await persona_generator_extractor.ainvoke(trustcall_input)

        if not (trustcall_result and trustcall_result.get("responses")):
            logger.error("Trustcall persona generator returned no valid response.")
            return None

        # Validate LLM output against PersonaBase
        llm_generated_data = trustcall_result["responses"][0]
        llm_generated_data.persona_id = (
            llm_generated_data.persona_id + f"_{uuid.uuid4().hex[:6]}"
        )

        persona_base_data = persona_schemas.PersonaBase.model_validate(
            llm_generated_data
        )
        logger.info(
            f"LLM generated valid PersonaBase data for ID: {persona_base_data.persona_id}"
        )
        return persona_base_data

    except ValidationError as e:
        logger.error(f"LLM output failed PersonaBase validation: {e}")
        logger.debug(f"Invalid LLM Output: {llm_generated_data}")
        return None
    except (IndexError, TypeError) as e:
        logger.error(f"Could not parse LLM response: {e}")
        logger.debug(
            f"Problematic LLM Response structure: {trustcall_result.get('responses')}"
        )
        return None
    except Exception as e:
        logger.exception(f"Unexpected error during LLM persona data generation: {e}")
        return None


async def _find_or_create_contact_for_persona(
    db: AsyncSession,
    account_id: uuid.UUID,
    persona_id_to_link: str,
    requested_identifier: Optional[str] = None,
) -> Optional[Contact]:
    """
    Finds or creates a contact based on the requested identifier,
    handling potential conflicts and marking as simulation contact.
    Args:
        db: The AsyncSession instance.
        account_id: The ID of the account the contact belongs to.
        requested_identifier: The identifier explicitly requested (can be None).
        persona_id_to_link: The persona_id we are trying to link to this contact.

    Returns:
        The found or created Contact object, or None if creation fails or
        if the contact exists but is linked to a *different* persona.

    Raises:
    ValueError: If the final identifier is invalid. TBD based on contact_repo validation
    """
    final_identifier: str

    if requested_identifier:
        final_identifier = requested_identifier
        logger.info(f"Using provided contact identifier: {final_identifier}")
    else:

        final_identifier = "5500" + "".join(random.choices("0123456789", k=9))
        logger.warning(
            f"LLM did not provide identifier, generated random one: {final_identifier}"
        )

    try:
        contact = await contact_repo.find_contact_by_identifier(
            db=db, identifier=final_identifier, account_id=account_id
        )
        if (
            contact
            and contact.persona
            and contact.persona.persona_id != persona_id_to_link
        ):
            logger.error(
                f"Contact identifier {final_identifier} (Contact ID: {contact.id}) "
                f"is already linked to a DIFFERENT persona: {contact.persona.persona_id}."
            )
            return None

        if not contact:
            logger.info(
                f"Contact with identifier {final_identifier} not found, creating..."
            )
            contact_data = ContactCreate(
                name=f"Persona: {persona_id_to_link}",
                phone_number=final_identifier,
                is_simulation=True,
            )
            contact = await contact_repo.create_contact(
                db=db,
                account_id=account_id,
                contact_data=contact_data,
            )
            if not contact:

                logger.error(
                    f"Failed to create contact for identifier {final_identifier}"
                )
                return None
            logger.info(
                f"Successfully created contact {contact.id} for identifier {final_identifier}"
            )

        else:
            logger.info(
                f"Found existing contact {contact.id} for identifier {final_identifier}"
            )

            if not contact.is_simulation:
                logger.warning(
                    f"Existing contact {contact.id} was not marked as simulation. Updating."
                )
                pass

        # Check for conflicting persona link AFTER finding or creating
        # Creating conversation and concat_inbox with the simulation inbox
        await create_conversation_from_contact(
            db=db, account_id=account_id, contact_id=contact.id
        )
        return contact

    except Exception as e:
        logger.exception(
            f"Error finding or creating contact for identifier {final_identifier}: {e}"
        )
        return None


async def create_conversation_from_contact(
    db: AsyncSession,
    account_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> None:

    # get the account
    account = await db.get(Account, account_id)

    if not account.simulation_inbox_id:
        logger.exception(f"No simulation inbox for the account: {account}")
        raise ValueError(f"No simulation inbox for the account: {account}")

    try:
        contact_inbox = await contact_repo.get_or_create_contact_inbox(
            db=db,
            account_id=account_id,
            contact_id=contact_id,
            inbox_id=account.simulation_inbox_id,
            source_id=f"simulation_setup_{uuid.uuid4().hex}",
        )

        conversation = await converastion_repo.get_or_create_conversation(
            db=db,
            account_id=account_id,
            inbox_id=account.simulation_inbox_id,
            contact_inbox_id=contact_inbox.id,
            status=ConversationStatusEnum.BOT,
        )

        conversation.is_simulation = True
        db.add(conversation)
        await db.flush()
        await db.refresh()
    except Exception as e:
        logger.exception(
            f"Unexpected error creating the contact inbox and the conversation for account: {account_id} and contact {contact_id}: {e}"
        )


async def save_persona_from_data(
    db: AsyncSession,
    persona_base_data: persona_schemas.PersonaBase,
    contact_id: uuid.UUID,
) -> Optional[persona_schemas.PersonaRead]:
    """
    Saves the persona data to the database, linking it to the provided contact_id.
    Args:
        db: The AsyncSession instance.
        persona_base_data: The validated PersonaBase data generated by the LLM.
        contact_id: The UUID of the Contact to link the persona to.

    Returns:
        A validated PersonaRead schema object for the created persona,
        or None if saving fails (e.g., duplicate persona_id).
    """
    logger.debug(
        f"Attempting to save persona '{persona_base_data.persona_id}' linked to contact {contact_id}"
    )
    try:
        # Prepare PersonaCreate payload
        persona_create_payload = persona_schemas.PersonaCreate(
            **persona_base_data.model_dump(),
            contact_id=contact_id,
        )

        # Create Persona in Database via Repository
        created_db_persona = await persona_repo.create_persona(
            db=db, persona_in=persona_create_payload
        )

        if created_db_persona is None:
            # create_persona logs the specific integrity error
            logger.error(
                f"Failed to save persona '{persona_create_payload.persona_id}' to database. Check previous logs for reason (e.g., duplicate ID)."
            )
            return None

        logger.success(
            f"Successfully saved persona: {created_db_persona.persona_id} (DB ID: {created_db_persona.id})"
        )
        return persona_schemas.PersonaRead.model_validate(created_db_persona)

    except ValidationError as e:
        logger.error(f"Failed to create PersonaCreate payload during save: {e}")
        return None
    except Exception as e:
        logger.exception(
            f"Unexpected error saving persona '{persona_base_data.persona_id}': {e}"
        )
        await db.rollback()  # Consider adding rollback if this function is used standalone
        return None


# --- Orchestrator Function ---
async def generate_and_save_persona(
    db: AsyncSession,
    account: Account,
    profile: CompanyProfileSchema,
    persona_type_description: str,
    contact_identifier: Optional[str] = None,
) -> Optional[persona_schemas.PersonaRead]:
    """
    Orchestrates the generation and saving of a persona.
    1. Generates persona base data using LLM.
    2. Finds or creates the associated Contact.
    3. Saves the Persona to the database linked to the Contact.

    Args:
        db: The AsyncSession instance.
        account: The Account object the persona belongs to.
        profile: The CompanyProfileSchema object for context.
        persona_type_description: Description of the desired persona type.
        contact_identifier: Optional specific identifier to use for the contact.
                        If None, uses the identifier suggested by the LLM, or
                        generates a random one as a last resort.

    Returns:
        A validated PersonaRead schema object for the created persona,
        or None if any step fails.
    """
    # 1. Generate Persona Base Data
    persona_base_data = await generate_persona_data(
        profile=profile, persona_type_description=persona_type_description
    )
    if not persona_base_data:
        logger.error("Persona data generation failed.")
        return None

    # 2. Find or Create Contact
    contact = await _find_or_create_contact_for_persona(
        db=db,
        account_id=account.id,
        requested_identifier=contact_identifier,
        persona_id_to_link=persona_base_data.persona_id,
    )
    if not contact:
        logger.error("Failed to find or create a valid contact for the persona.")

        await db.rollback()
        return None

    # 3. Save Persona linked to Contact
    try:
        saved_persona = await save_persona_from_data(
            db=db,
            persona_base_data=persona_base_data,
            contact_id=contact.id,
        )

        if saved_persona:
            await db.commit()
            logger.info(
                f"Successfully committed persona {saved_persona.persona_id} and contact operations."
            )
            return saved_persona
        else:
            logger.error("Failed to save persona data to the database.")
            await db.rollback()
            return None
    except Exception as e:
        logger.exception(f"Error during final persona saving or commit: {e}")
        await db.rollback()
        return None
