# backend/app/simulation/personas/generator.py

import json
import uuid  # Import uuid
from typing import Optional, List, Any, Dict  # Import Dict
import random

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession  # Import AsyncSession

from langchain_openai import ChatOpenAI
from trustcall import create_extractor

# --- Import New Schemas and Repositories ---

from app.simulation.schemas import persona as persona_schemas  # Use new schemas
from app.api.schemas.company_profile import CompanyProfileSchema
from app.simulation.repositories import persona as persona_repo  # Import persona repo
from app.api.schemas.contact import ContactCreate
from app.services.repository import (
    contact as contact_repo,
)  # Assuming contact repo exists
from app.models.contact import Contact  # Import Contact model
from app.models.account import Account  # Import Account model for type hint

# --- LLM and Trustcall setup ---
# Configure extractor to use PersonaBase
try:
    llm_generator = ChatOpenAI(model="gpt-4o", temperature=0.7)

    persona_generator_extractor: Optional[Any] = create_extractor(
        llm_generator,
        tools=[persona_schemas.PersonaBase],  # Target PersonaBase schema
        tool_choice="PersonaBase",  # Target PersonaBase schema
        enable_inserts=True,
    )

    logger.info("Trustcall extractor for PersonaBase generation initialized.")
except Exception as e:
    logger.error(f"Failed to initialize LLM or Trustcall extractor for generation: {e}")
    persona_generator_extractor = None


# --- Updated Prompt ---
# Minor change: Reference PersonaBase fields, removed explicit mention of identifier generation rule
GENERATOR_SYSTEM_PROMPT_PT = """
SYSTEM: Você é um especialista em marketing e vendas B2C, encarregado de criar perfis de personas de clientes realistas para simular interações de vendas via WhatsApp. Seu objetivo é gerar UMA definição de persona em formato JSON que será usada para testar um assistente de vendas de IA.

TASK: Com base no perfil da empresa fornecido abaixo e no **tipo de persona desejado**, gere UM objeto JSON contendo os campos para uma persona de cliente (`persona_id`, `description`, `initial_message`, `objective`, `information_needed`, `info_attribute_to_question_template`, `success_criteria`, `failure_criteria`). A persona deve ser relevante para o público-alvo e as ofertas da empresa. Gere também um `simulation_contact_identifier` plausível (formato '55[DDD][9 dígitos]').

**TIPO DE PERSONA DESEJADO: {persona_type_description}**

REGRAS PARA GERAÇÃO DOS DADOS DA PERSONA:
1.  **Relevância:** A persona (descrição, mensagem inicial, objetivo) deve ser plausível e diretamente relacionada ao negócio descrito no perfil da empresa. Considere o `target_audience` e o `offering_overview`. Crie personas variadas.
2.  **`persona_id`:** Crie um ID descritivo em formato snake_case (e.g., 'cliente_curioso_bolo', 'comprador_rapido_pao'). Deve ser único.
3.  **`simulation_contact_identifier`:** Gere um identificador único e plausível no formato '55[DDD_valido][9_digitos_aleatorios]' (e.g., '5511987654321').
4.  **`description`:** Escreva uma descrição concisa (1 frase).
5.  **`initial_message`:** Crie uma primeira mensagem natural e curta.
6.  **`objective`:** Defina um objetivo claro e específico.
7.  **`information_needed`:** Liste os fatos específicos (objetos com 'entity' e 'attribute') que a persona precisa.
8.  **`info_attribute_to_question_template`:** Para CADA atributo *único* em `information_needed`, crie uma entrada neste dicionário (template de pergunta com `{{entity}}` se aplicável).
9.  **Critérios:** Use `success_criteria` (e.g., `["state:all_info_extracted"]`) e `failure_criteria` (e.g., `["event:ai_fallback_detected", "turn_count > 8"]`).

PERFIL DA EMPRESA (CONTEXTO):
```json
{company_profile_json}
```
Use code with caution.
Python
INSTRUÇÃO FINAL: Gere APENAS o objeto JSON contendo os campos da persona conforme as regras acima. Não inclua nenhum outro texto ou explicação.
"""


# --- Updated Generation Function ---
async def generate_and_save_persona(
    db: AsyncSession,
    account: Account,  # Pass the full Account object or just account_id
    profile: CompanyProfileSchema,
    persona_type_description: str,
    contact_identifier: Optional[str],
) -> Optional[persona_schemas.PersonaRead]:
    """
    Generates persona data using an LLM, creates/finds the associated Contact,
    saves the Persona to the database, and returns the saved Persona data.
    Args:
        db: The AsyncSession instance.
        account: The Account object the persona belongs to.
        profile: The CompanyProfileSchema object for context.
        persona_type_description: Description of the desired persona type.

    Returns:
        A validated PersonaRead schema object for the created persona,
        or None if generation or saving fails.
    """
    if not persona_generator_extractor:
        logger.error("Persona generator extractor not available.")
        return None
    if not account:
        logger.error("Account information is required to create a persona.")
        return None

    account_id = account.id
    logger.info(
        f"Generating persona for account: {account_id}, company: {profile.company_name}"
    )

    try:
        # 1. Generate Persona Base Data using LLM
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

        # --- Validate LLM output against PersonaBase ---
        try:
            # Expecting the first response to be the generated data
            llm_generated_data = trustcall_result["responses"][0]
            # Validate and parse the data into PersonaBase
            # NOTE: This instance is temporary, just for validation and data extraction
            persona_base_data = persona_schemas.PersonaBase.model_validate(
                llm_generated_data
            )
            logger.info(
                f"LLM generated valid PersonaBase data for ID: {persona_base_data.persona_id}"
            )
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

        # 2. Handle the Contact
        generated_identifier = persona_base_data.simulation_contact_identifier
        if not generated_identifier:
            logger.error("LLM did not generate a simulation_contact_identifier.")
            return None

        try:
            # WARNING: Ensure contact_repo.get_or_create_simulation_contact handles potential
            # race conditions if run concurrently and correctly checks if an existing contact
            # is already linked to a DIFFERENT persona. It should also mark the contact
            # as is_simulation=True.

            if contact_identifier is None:
                generated_identifier = "5500" + "".join(
                    random.choices("0123456789", k=9)
                )

            contact = await contact_repo.find_contact_by_identifier(
                db=db, identifier=contact_identifier, account_id=account_id
            )

            if not contact:
                contact = await contact_repo.create_contact(
                    db=db,
                    account_id=account_id,
                    contact_data=ContactCreate(
                        name=f"Persona: {persona_base_data.persona_id}",
                        phone_number=contact_identifier,
                        is_simulation=True,
                    ),
                )
                if not contact:
                    logger.error(
                        f"Failed to get or create contact for identifier {contact_identifier}"
                    )
                    return None

            if (
                contact.persona
                and contact.persona.persona_id != persona_base_data.persona_id
            ):  # Check if linked to *another* persona
                logger.error(
                    f"Contact identifier {generated_identifier} is already linked to persona {contact.persona.persona_id}."
                )
                # Consider retrying generation with a different identifier? For now, fail.
                return None

            logger.info(
                f"Using Contact ID: {contact.id} for identifier {generated_identifier}"
            )
            contact_id = contact.id

        except Exception as e:
            logger.exception(
                f"Error finding or creating contact for identifier {generated_identifier}: {e}"
            )
            return None

        # 3. Prepare PersonaCreate payload
        try:
            persona_create_payload = persona_schemas.PersonaCreate(
                **persona_base_data.model_dump(),  # Unpack validated base data
                contact_id=contact_id,  # Add the obtained contact_id
            )
        except ValidationError as e:
            # Should not happen if PersonaBase validated, but good safety check
            logger.error(
                f"Failed to create PersonaCreate payload (should not happen): {e}"
            )
            return None

        # 4. Create Persona in Database via Repository
        # The repository handles uniqueness checks for persona_id, contact_id etc.
        created_db_persona = await persona_repo.create_persona(
            db=db, persona_in=persona_create_payload
        )

        if created_db_persona is None:
            # create_persona logs the specific integrity error (e.g., duplicate persona_id)
            logger.error(
                f"Failed to save persona '{persona_create_payload.persona_id}' to database. Check previous logs for reason (e.g., duplicate ID)."
            )
            return None

        # 5. Return the Saved Persona Data (as PersonaRead)
        logger.success(
            f"Successfully generated and saved persona: {created_db_persona.persona_id} (DB ID: {created_db_persona.id})"
        )
        # Convert ORM model to PersonaRead schema
        return persona_schemas.PersonaRead.model_validate(created_db_persona)

    except ValidationError as e:
        # Catch validation errors during the final payload creation (less likely)
        logger.error(
            f"Generated persona failed Pydantic validation during final creation: {e}"
        )
        return None
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during persona generation and saving: {e}"
        )
        await db.rollback()  # Rollback any potential partial transaction
        return None
