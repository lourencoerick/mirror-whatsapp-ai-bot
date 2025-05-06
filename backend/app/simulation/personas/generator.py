# backend/app/simulation/personas/generator.py

import json
import uuid
import random
from typing import Optional, List, Any, Dict

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_openai import AzureChatOpenAI
from trustcall import create_extractor


from app.simulation.schemas import persona as persona_schemas
from app.api.schemas.company_profile import CompanyProfileSchema
from app.simulation.repositories import persona as persona_repo


from app.api.schemas.contact import ContactCreate
from app.services.repository import contact as contact_repo
from app.services.repository import conversation as conversation_repo
from app.models.conversation import ConversationStatusEnum
from app.models.contact import Contact
from app.models.account import Account

from app.config import get_settings, Settings

settings: Settings = get_settings()

GENERATOR_SYSTEM_PROMPT_PT = """
SYSTEM: Você é um especialista em marketing e vendas B2C, criando perfis de personas realistas para simular interações de vendas via WhatsApp. Seu objetivo é gerar UMA definição de persona em formato JSON.

TASK: Com base no perfil da empresa e no **tipo de persona desejado**, gere UM objeto JSON contendo os campos da persona (`persona_id`, `description`, `initial_message`, `objective`, `information_needed`, `potential_objections`, `off_topic_questions`, `behavior_hints`, `success_criteria`, `failure_criteria`). A persona deve ser relevante para o negócio. O `simulation_contact_identifier` será definido depois.

**TIPO DE PERSONA DESEJADO: {persona_type_description}**

REGRAS PARA GERAÇÃO DOS DADOS DA PERSONA:
1.  **Relevância:** Persona, mensagem inicial, objetivo, informações, objeções e comportamento devem ser plausíveis e relacionados ao negócio. Considere `target_audience` e `offering_overview`. Crie variedade.
2.  **`persona_id`:** ID descritivo em snake_case (será adicionado sufixo único depois).
3.  **`description`:** Descrição concisa (1 frase).
4.  **`initial_message`:** Primeira mensagem natural e curta.
5.  **`objective`:** Objetivo claro e específico que a persona quer alcançar na conversa.
6.  **`information_needed`:** Liste 1-3 fatos *contextuais* que a persona *pode* querer saber ({{'entity': 'X', 'attribute': 'Y'}}). Pode ser uma lista vazia se o objetivo for outro (ex: apenas testar objeções).
7.  **`potential_objections`:** Liste 1-3 objeções *plausíveis* que esta persona poderia levantar. Para cada uma, defina `objection_text`. Opcionalmente, defina `trigger_keyword` ou `trigger_stage`.
8.  **`off_topic_questions`:** Liste 1-3 perguntas *realistas* fora do tópico principal que a persona poderia fazer.
9.  **`behavior_hints`:** Liste 2-4 palavras-chave que descrevam o comportamento (ex: 'impaciente', 'detalhista', 'confuso_facilmente', 'amigável', 'cético', 'decidido', 'comparador').
10. **Critérios:** Use `success_criteria` (geralmente vazio agora) e `failure_criteria` (e.g., `["event:ai_fallback_detected", "turn_count > 10"]`).

PERFIL DA EMPRESA (CONTEXTO):
```json
{company_profile_json}
```
Use code with caution.
Python
INSTRUÇÃO FINAL: Gere APENAS o objeto JSON contendo os campos da persona conforme as regras acima. NÃO inclua info_attribute_to_question_template.
"""


async def generate_persona_data(
    profile: CompanyProfileSchema,
    persona_type_description: str,
) -> Optional[persona_schemas.PersonaBase]:
    """
    Generates persona base data using the LLM based on company profile.
    """
    logger.debug(f"Generating persona data for type: {persona_type_description}")
    persona_generator_extractor: Optional[Any] = None
    try:

        llm_gen = AzureChatOpenAI(
            azure_deployment="gpt-4o",
            temperature=0.7,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2025-01-01-preview",
        )
        persona_generator_extractor = create_extractor(
            llm_gen,
            tools=[persona_schemas.PersonaBase],
            tool_choice="PersonaBase",
        )
        logger.info("Temporary extractor for PersonaBase generation initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize LLM or extractor: {e}")
        return None

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

        llm_generated_data_dict = trustcall_result["responses"][0]
        if not isinstance(llm_generated_data_dict, dict):
            if isinstance(llm_generated_data_dict, persona_schemas.PersonaBase):
                llm_generated_data_dict = llm_generated_data_dict.model_dump()
            else:
                logger.error(
                    f"Extractor returned unexpected type: {type(llm_generated_data_dict)}"
                )
                return None

        base_persona_id = llm_generated_data_dict.get("persona_id", "unknown_persona")
        base_persona_id = "".join(
            c if c.isalnum() or c == "_" else "_" for c in base_persona_id.lower()
        ).strip("_")
        unique_persona_id = f"{base_persona_id}_{uuid.uuid4().hex[:6]}"
        llm_generated_data_dict["persona_id"] = unique_persona_id

        llm_generated_data_dict.pop("info_attribute_to_question_template", None)

        persona_base_data = persona_schemas.PersonaBase.model_validate(
            llm_generated_data_dict
        )
        logger.info(
            f"LLM generated valid PersonaBase data for ID: {persona_base_data.persona_id}"
        )
        return persona_base_data

    except ValidationError as e:
        logger.error(f"LLM output failed PersonaBase validation: {e}")
        logger.debug(f"Invalid LLM Output Dict: {llm_generated_data_dict}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error during LLM persona data generation: {e}")
        return None


async def _find_or_create_contact_for_persona(
    db: AsyncSession,
    account_id: uuid.UUID,
    persona_id_to_link: str,
) -> Optional[Contact]:
    """Finds or creates a simulation contact."""
    final_identifier = "5500" + "".join(random.choices("0123456789", k=9))
    logger.info(f"Using generated simulation identifier: {final_identifier}")

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
                f"Generated identifier {final_identifier} conflict: linked to persona {contact.persona.persona_id}."
            )

            return None
        if not contact:
            contact_data = ContactCreate(
                name=f"Persona: {persona_id_to_link}",
                phone_number=final_identifier,
                is_simulation=True,
            )
            contact = await contact_repo.create_contact(
                db=db, account_id=account_id, contact_data=contact_data
            )
            if not contact:
                logger.error(
                    f"Failed to create contact for identifier {final_identifier}"
                )
                return None
            logger.info(
                f"Created contact {contact.id} for identifier {final_identifier}"
            )
        else:
            logger.info(
                f"Found existing contact {contact.id} for identifier {final_identifier}"
            )
            if not contact.is_simulation:
                logger.warning(
                    f"Existing contact {contact.id} not marked as simulation. Updating."
                )

                pass

        await create_conversation_from_contact(
            db=db, account_id=account_id, contact_id=contact.id
        )
        return contact
    except Exception as e:
        logger.exception(
            f"Error finding or creating contact for identifier {final_identifier}: {e}"
        )
        return None


async def save_persona_from_data(
    db: AsyncSession,
    persona_base_data: persona_schemas.PersonaBase,
    contact_id: uuid.UUID,
) -> Optional[persona_schemas.PersonaRead]:
    """Saves the persona data to the database, linking it to the contact_id."""
    logger.debug(
        f"Attempting to save persona '{persona_base_data.persona_id}' linked to contact {contact_id}"
    )
    try:
        persona_create_payload = persona_schemas.PersonaCreate(
            **persona_base_data.model_dump(),
            contact_id=contact_id,
        )
        created_db_persona = await persona_repo.create_persona(
            db=db, persona_in=persona_create_payload
        )
        if created_db_persona is None:
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
        await db.rollback()
        return None


async def generate_and_save_persona(
    db: AsyncSession,
    account: Account,
    profile: CompanyProfileSchema,
    persona_type_description: str,
) -> Optional[persona_schemas.PersonaRead]:
    """Orchestrates the generation and saving of a persona."""
    # 1. Generate Persona Base Data
    persona_base_data = await generate_persona_data(
        profile=profile, persona_type_description=persona_type_description
    )
    if not persona_base_data:
        return None

    # 2. Find or Create Contact
    contact = await _find_or_create_contact_for_persona(
        db=db,
        account_id=account.id,
        persona_id_to_link=persona_base_data.persona_id,
    )
    if not contact:
        await db.rollback()
        return None  # Rollback se contato falhar

    # 3. Save Persona linked to Contact
    try:
        saved_persona = await save_persona_from_data(
            db=db, persona_base_data=persona_base_data, contact_id=contact.id
        )
        if saved_persona:
            await db.commit()  # Commit final apenas se tudo deu certo
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


async def create_conversation_from_contact(
    db: AsyncSession, account_id: uuid.UUID, contact_id: uuid.UUID
) -> None:
    """Creates contact_inbox and conversation for a simulation contact."""
    account = await db.get(Account, account_id)
    if not account or not account.simulation_inbox_id:
        logger.exception(f"Account {account_id} or its simulation_inbox_id not found.")
        raise ValueError(f"Account {account_id} or simulation inbox missing.")

    try:
        contact_inbox = await contact_repo.get_or_create_contact_inbox(
            db=db,
            account_id=account_id,
            contact_id=contact_id,
            inbox_id=account.simulation_inbox_id,
            source_id=f"simulation_setup_{uuid.uuid4().hex}",
        )
        conversation = await conversation_repo.get_or_create_conversation(
            db=db,
            account_id=account_id,
            inbox_id=account.simulation_inbox_id,
            contact_inbox_id=contact_inbox.id,
            status=ConversationStatusEnum.BOT,
        )
        if not conversation.is_simulation:
            conversation.is_simulation = True
            db.add(conversation)
            await db.flush()
            await db.refresh(conversation)
            logger.info(f"Marked conversation {conversation.id} as simulation.")
        else:
            logger.debug(
                f"Conversation {conversation.id} already marked as simulation."
            )

    except Exception as e:
        logger.exception(
            f"Error creating contact_inbox/conversation for contact {contact_id}: {e}"
        )

        raise
