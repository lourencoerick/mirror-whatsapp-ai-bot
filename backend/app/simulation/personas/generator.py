# backend/app/simulation/personas/generator.py

import json
from typing import Optional, List, Any

from loguru import logger
from pydantic import ValidationError

from langchain_openai import ChatOpenAI
from trustcall import create_extractor


from app.simulation.schemas.persona_definition import PersonaDefinition
from app.api.schemas.company_profile import CompanyProfileSchema


# --- LLM and Trustcall setup ---
try:
    llm_generator = ChatOpenAI(model="gpt-4o", temperature=0.7)

    persona_generator_extractor: Optional[Any] = create_extractor(
        llm_generator,
        tools=[PersonaDefinition],
        tool_choice="PersonaDefinition",
        enable_inserts=True,
    )

    logger.info("Trustcall extractor for PersonaDefinition generation initialized.")
except Exception as e:
    logger.error(f"Failed to initialize LLM or Trustcall extractor for generation: {e}")
    persona_generator_extractor = None

# --- Prompt in Portuguese ---
GENERATOR_SYSTEM_PROMPT_PT = """
SYSTEM: Você é um especialista em marketing e vendas B2C, encarregado de criar perfis de personas de clientes realistas para simular interações de vendas via WhatsApp. Seu objetivo é gerar UMA definição de persona em formato JSON que será usada para testar um assistente de vendas de IA.

TASK: Com base no perfil da empresa fornecido abaixo e no **tipo de persona desejado**, gere UMA definição de persona de cliente (PersonaDefinition) em formato JSON. A persona deve ser relevante para o público-alvo e as ofertas da empresa.

**TIPO DE PERSONA DESEJADO: {persona_type_description}**

REGRAS PARA GERAÇÃO DA PERSONA:
1.  **Relevância:** A persona (descrição, mensagem inicial, objetivo) deve ser plausível e diretamente relacionada ao negócio descrito no perfil da empresa. Considere o `target_audience` e o `offering_overview`. Crie personas variadas (algumas decididas, outras curiosas, outras focadas em preço, etc.).
2.  **`persona_id`:** Crie um ID descritivo em formato snake_case (e.g., 'cliente_curioso_bolo', 'comprador_rapido_pao').
3.  **`simulation_contact_identifier`:** Gere um identificador único e plausível no formato '55[DDD_valido][9_digitos_aleatorios]' (e.g., '5511987654321'). Use DDDs comuns como 11, 21, 31, etc.
4.  **`description`:** Escreva uma descrição concisa (1 frase) sobre a persona e seu objetivo principal.
5.  **`initial_message`:** Crie uma primeira mensagem natural e curta que a persona enviaria via WhatsApp.
6.  **`objective`:** Defina um objetivo claro e específico que a persona quer alcançar na conversa (e.g., "Obter preço e disponibilidade do item X", "Entender se o serviço Y serve para meu caso", "Comparar opções A e B").
7.  **`information_needed`:** Liste os fatos específicos (objetos com 'entity' e 'attribute') que a persona precisa descobrir para atingir seu `objective`. As entidades devem ser nomes de produtos/serviços do `offering_overview` ou tópicos gerais relevantes (e.g., 'entrega', 'horario_funcionamento'). Os atributos devem ser chaves concisas (e.g., 'price', 'size', 'availability', 'options', 'details').
8.  **`info_attribute_to_question_template`:** Para CADA atributo *único* listado em `information_needed`, crie uma entrada neste dicionário. A chave é o nome do atributo, e o valor é um *template* de pergunta natural que a persona usaria, incluindo o placeholder `{{entity}}` onde apropriado (e.g., "Qual o preço de {{entity}}?", "Como funciona a {{entity}}?").
9.  **Critérios:** Use os padrões: `success_criteria` como `["state:all_info_extracted"]` e `failure_criteria` como `["event:ai_fallback_detected", "turn_count > 8"]`.

PERFIL DA EMPRESA (CONTEXTO):
```json
{company_profile_json}
```
INSTRUÇÃO FINAL: Gere APENAS o objeto JSON da PersonaDefinition correspondente às regras acima. Não inclua nenhum outro texto ou explicação.
"""

# --- Função Principal de Geração ---


async def generate_persona_definition(
    profile: CompanyProfileSchema,
    persona_type_description: str,
    existing_persona_ids: Optional[List[str]] = None,
) -> Optional[PersonaDefinition]:
    """
    Generates a PersonaDefinition using an LLM based on a CompanyProfile.

    Args:
        profile: The CompanyProfileSchema object for context.
        existing_persona_ids: Optional list of existing persona IDs to avoid collision.

    Returns:
        A validated PersonaDefinition object, or None if generation fails.
    """
    if not persona_generator_extractor:
        logger.error("Persona generator extractor not available.")
        return None

    logger.info(f"Generating persona definition for company: {profile.company_name}")

    try:
        profile_json_str = profile.model_dump_json(indent=2)
        prompt = GENERATOR_SYSTEM_PROMPT_PT.format(
            company_profile_json=profile_json_str,
            persona_type_description=persona_type_description,
        )

        trustcall_input = {"messages": [{"role": "system", "content": prompt}]}

        logger.debug("Calling trustcall persona generator extractor...")
        trustcall_result = await persona_generator_extractor.ainvoke(trustcall_input)

        if trustcall_result and trustcall_result.get("responses"):
            persona_data = trustcall_result["responses"][0]

            if isinstance(persona_data, PersonaDefinition):
                if (
                    existing_persona_ids
                    and persona_data.persona_id in existing_persona_ids
                ):
                    logger.warning(
                        f"Generated persona_id '{persona_data.persona_id}' already exists. Consider regeneration."
                    )

                    return None

                logger.success(
                    f"Successfully generated and validated persona: {persona_data.persona_id}"
                )
                return persona_data
            else:
                logger.error(
                    f"Trustcall returned unexpected type for persona: {type(persona_data)}"
                )
                return None
        else:
            logger.error("Trustcall persona generator returned no valid response.")
            return None

    except ValidationError as e:
        logger.error(f"Generated persona failed Pydantic validation: {e}")
        return None
    except Exception as e:
        logger.exception(f"An unexpected error occurred during persona generation: {e}")
        return None
