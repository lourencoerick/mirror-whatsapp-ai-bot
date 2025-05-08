# backend/app/services/ai_reply/new_agent/components/response_generator.py

from typing import Dict, List, Optional, Any
from loguru import logger
import json

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Importar definições de estado e tipos
from ..state_definition import (
    RichConversationState,
    AgentActionType,
    AgentActionDetails,
    CompanyProfileSchema,
    SpinQuestionType,  # Para type hint
    AgentGoal,  # Para obter detalhes do goal se necessário
)

# Importar utils de prompt
from ..prompt_utils import WHATSAPP_MARKDOWN_INSTRUCTIONS
from app.api.schemas.company_profile import CompanyProfileSchema

# Importar função auxiliar de formatação de histórico
# (Idealmente de um módulo utils)
try:
    from .input_processor import _format_recent_chat_history
except ImportError:  # Fallback se a estrutura mudar

    def _format_recent_chat_history(*args, **kwargs) -> str:
        return "Histórico indisponível."


# --- Prompts (Definidos anteriormente, podem ser movidos para um módulo de prompts) ---

PROMPT_ANSWER_DIRECT_QUESTION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA para '{company_name}'.
Seu objetivo é responder à pergunta específica do cliente de forma precisa e completa, usando o 'Contexto Relevante' (se disponível) e o 'Perfil da Empresa'.
Comunique-se em {language} com um tom {sales_tone}. Siga as diretrizes de formatação.

**Pergunta Específica do Cliente:**
{question_to_answer}

**Contexto Relevante (RAG - Use se ajudar a responder):**
{rag_context}

**Informações do Perfil da Empresa (Use se RAG não for suficiente):**
Descrição: {business_description}
Ofertas: {offering_summary}
{company_address_info}
{opening_hours_info}
Diretrizes: {communication_guidelines}

**Instruções:**
1. Use o Contexto RAG primeiro, se relevante e útil para responder DIRETAMENTE à pergunta.
2. Se não, use o Perfil da Empresa.
3. Se ainda não souber a resposta EXATA, use o texto de fallback: '{fallback_text}'
4. Seja direto e responda APENAS à pergunta feita. NÃO adicione perguntas de acompanhamento ou encerramento neste passo.
5. Aplique a formatação WhatsApp: {formatting_instructions}

HISTÓRICO RECENTE (Contexto):
{chat_history}

Responda à pergunta '{question_to_answer}'.""",
        ),
    ]
)

PROMPT_ASK_SPIN_QUESTION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA conversacional, especialista em SPIN Selling.
Sua tarefa é gerar a PRÓXIMA pergunta da conversa, do tipo '{spin_type}'.

**Contexto:**
Última Mensagem do Cliente (Aproximada): {last_user_message} 
Tipo de Pergunta SPIN a ser Gerada: {spin_type}
Tom de Vendas: {sales_tone}
Idioma: {language}

**Instruções:**
1. Gere UMA pergunta clara, aberta e específica do tipo '{spin_type}'.
2. Tente conectar a pergunta ao tópico da última mensagem do cliente, se possível, de forma natural.
3. Use formatação WhatsApp sutil: {formatting_instructions}

PERFIL DA EMPRESA (Contexto): Nome: {company_name}, Descrição: {business_description}
HISTÓRICO RECENTE:
{chat_history}

Gere APENAS a pergunta SPIN do tipo '{spin_type}'.""",
        ),
    ]
)

PROMPT_GENERATE_REBUTTAL = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA experiente em superar objeções com empatia e lógica.
O cliente levantou a seguinte objeção: **"{objection_text}"**.

**Contexto Relevante (RAG - Use para embasar sua resposta):**
{rag_context}

**Informações da Empresa (Use para reforçar valor/credibilidade):**
Nome: {company_name}
Descrição: {business_description}
Pontos Chave: {key_selling_points}
Tom: {sales_tone}
Idioma: {language}

**Instruções:**
1. **Valide/Empatize:** Comece reconhecendo a preocupação do cliente de forma genuína e específica.
2. **Refute/Reenquadre:** Use o Contexto RAG e as Informações da Empresa para abordar a objeção diretamente, destacar valor, esclarecer mal-entendidos ou oferecer soluções/alternativas. Seja CONCRETO se tiver informações.
3. **Verifique:** Termine com uma pergunta curta e aberta para verificar o entendimento ou propor um próximo passo suave. (Ex: "Isso faz mais sentido?", "O que você acha dessa perspectiva?", "Podemos explorar como [benefício] supera isso?"). NÃO use apenas "Posso ajudar com algo mais?".
4. **Formatação:** Aplique formatação WhatsApp sutil: {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Gere a resposta para a objeção '{objection_text}'.""",
        ),
    ]
)

PROMPT_ASK_CLARIFYING_QUESTION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA empático. O cliente fez uma declaração vaga ou expressou dúvida não específica:
**"{vague_statement_text}"**

Sua tarefa é fazer **UMA única pergunta aberta** para entender melhor o que o cliente quis dizer ou qual é a sua preocupação/dúvida principal. Mantenha um tom {sales_tone} e use o idioma {language}.

**Exemplos:** "Para que eu possa te ajudar melhor, poderia me dizer um pouco mais sobre o que está pensando?", "O que especificamente sobre [tópico, se houver] te deixou com dúvidas?", "Pode elaborar um pouco mais?".

Use formatação WhatsApp sutil: {formatting_instructions}

Gere APENAS a pergunta clarificadora.""",
        ),
    ]
)

PROMPT_ACKNOWLEDGE_AND_TRANSITION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA focado em manter a conversa produtiva. O cliente fez um comentário fora do tópico principal da conversa: "{off_topic_text}".
Sua tarefa é:
1. **Reconhecer Brevemente:** Faça um comentário curto e neutro sobre o que o cliente disse (Ex: "Entendido.", "Interessante ponto."). NÃO se aprofunde no tópico off-topic.
2. **Transicionar de Volta:** Gentilmente redirecione a conversa para o objetivo anterior ou para o próximo passo lógico da venda. Use o 'Tópico do Objetivo Anterior' para contexto. (Ex: "Voltando ao que conversávamos sobre {previous_goal_topic}...", "Continuando de onde paramos...", "Para seguirmos, podemos falar sobre {previous_goal_topic}?").
3. Mantenha o tom {sales_tone} e use o idioma {language}.
4. Use formatação WhatsApp sutil: {formatting_instructions}

Tópico do Objetivo Anterior: {previous_goal_topic}

Gere APENAS a frase curta de reconhecimento e transição.""",
        ),
    ]
)

PROMPT_PRESENT_SOLUTION_OFFER = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA focado em apresentar soluções que resolvem necessidades identificadas do cliente.
O objetivo é apresentar o '{product_name_to_present}' destacando como ele atende ao '{key_benefit_to_highlight}'.

**Contexto:**
Produto a Apresentar: {product_name_to_present}
Benefício Chave a Destacar: {key_benefit_to_highlight}
Tom de Vendas: {sales_tone}
Idioma: {language}

**Informações do Perfil da Empresa (Use para detalhes do produto, se necessário):**
Nome da Empresa: {company_name}
Descrição do Negócio: {business_description}
Ofertas (pode conter detalhes do produto): {offering_summary} 
Pontos Chave de Venda Gerais: {key_selling_points}

**Contexto Adicional (RAG - Use se fornecer detalhes específicos sobre o produto/benefício):**
{rag_context}

**Instruções:**
1. Comece conectando a solução à necessidade/benefício. (Ex: "Com base no que conversamos sobre [benefício/necessidade], a solução ideal para você seria o nosso {product_name_to_present}.")
2. Descreva brevemente o {product_name_to_present} e COMO ele entrega o {key_benefit_to_highlight}. Use informações do RAG ou das Ofertas se disponíveis.
3. Foque nos benefícios para o cliente, não apenas nas características.
4. Termine com uma pergunta de transição suave para verificar o interesse ou convidar a uma próxima etapa (Ex: "Isso parece algo que atenderia às suas expectativas?", "Gostaria de ver como isso funciona na prática?", "O que acha de explorarmos essa opção mais a fundo?").
5. Aplique formatação WhatsApp: {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Apresente o '{product_name_to_present}' focando no benefício '{key_benefit_to_highlight}'.""",
        ),
    ]
)

PROMPT_INITIATE_CLOSING = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA prestativo e eficiente, pronto para finalizar a venda.
Sua tarefa é iniciar o processo de fechamento de forma clara e convidativa.

**Contexto:**
Tom de Vendas: {sales_tone}
Idioma: {language}
Produto/Proposta (se disponível): {product_name_price_info}

**Instruções:**
1.  Confirme o interesse do cliente com base na conversa anterior (ex: "Que ótimo que gostou!", "Perfeito!").
2.  Pergunte diretamente se o cliente gostaria de prosseguir com a compra/pedido do {product_name_fallback}.
3.  Seja claro e direto ao ponto.
4.  Use formatação WhatsApp sutil: {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Gere a mensagem para iniciar o fechamento.""",
        ),
    ]
)

PROMPT_CONFIRM_ORDER_DETAILS = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA confirmando os detalhes finais antes de prosseguir.
Sua tarefa é reconfirmar o item principal e o preço, e pedir a confirmação final do cliente.

**Contexto:**
Tom de Vendas: {sales_tone}
Idioma: {language}
Produto a Confirmar: {product_name}
Preço a Confirmar: {price_info}

**Instruções:**
1.  Agradeça a confirmação anterior do cliente.
2.  Reafirme claramente o produto/plano e o preço/condição principal. Ex: "Só para confirmar, estamos prosseguindo com o *{product_name}* pelo valor de {price_info}."
3.  Peça uma confirmação final para prosseguir para a próxima etapa (que pode ser coleta segura de dados, link de pagamento, etc.). Ex: "Está tudo correto para seguirmos?", "Posso prosseguir com a criação do seu pedido/link?", "Confirma estes detalhes para finalizarmos?".
4.  Use formatação WhatsApp sutil: {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Gere a mensagem de confirmação dos detalhes.""",
        ),
    ]
)


PROMPT_PROCESS_ORDER_CONFIRMATION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA confirmando o sucesso do pedido.
Sua tarefa é informar ao cliente que o pedido foi processado com sucesso (ou que os próximos passos foram iniciados).

**Contexto:**
Tom de Vendas: {sales_tone}
Idioma: {language}
Produto Confirmado: {product_name}

**Instruções:**
1.  Confirme que o pedido do *{product_name}* foi recebido/processado com sucesso.
2.  Mencione brevemente os próximos passos, se houver (ex: "Você receberá um email de confirmação em breve.", "Nossa equipe entrará em contato para agendar."). Se não houver próximos passos claros, apenas confirme o sucesso.
3.  Agradeça ao cliente pela compra.
4.  Use formatação WhatsApp sutil: {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Gere a mensagem de confirmação do pedido.""",
        ),
    ]
)

PROMPT_GENERATE_FAREWELL = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA encerrando a conversa de forma cordial.
Sua tarefa é gerar uma mensagem de despedida apropriada.

**Contexto:**
Tom de Vendas: {sales_tone}
Idioma: {language}
Motivo do Encerramento (Opcional): {reason}

**Instruções:**
1.  Se houver um motivo específico (ex: impasse, rejeição), reconheça-o brevemente e com empatia, se apropriado.
2.  Agradeça ao cliente pelo tempo/conversa.
3.  Ofereça ajuda futura ou um próximo passo alternativo, se aplicável (ex: "Se mudar de ideia ou tiver outras dúvidas, estou à disposição.", "Você pode encontrar mais informações em nosso site: {fallback_contact_info}").
4.  Deseje um bom dia/tarde/noite.
5.  Use formatação WhatsApp sutil: {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Gere a mensagem de despedida.""",
        ),
    ]
)


PROMPT_HANDLE_CLOSING_CORRECTION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA atencioso, ajudando o cliente a corrigir detalhes do pedido.
O cliente indicou que algo precisa ser corrigido durante o processo de fechamento.

**Contexto:**
Tom de Vendas: {sales_tone}
Idioma: {language}
Contexto da Correção: {context}

**Instruções:**
1.  Peça desculpas pelo erro ou mal-entendido de forma breve. (Ex: "Peço desculpas por isso.", "Entendido, vamos corrigir.")
2.  Peça ao cliente para especificar *exatamente* o que precisa ser alterado. (Ex: "Poderia me dizer qual informação precisa ser corrigida?", "O que exatamente precisamos ajustar no pedido?").
3.  Seja prestativo e claro.
4.  Use formatação WhatsApp sutil: {formatting_instructions}

HISTÓRICO RECENTE:
{chat_history}

Gere a mensagem para solicitar os detalhes da correção.""",
        ),
    ]
)

# --- Mapeamento de Ação para Prompt ---
ACTION_TO_PROMPT_MAP: Dict[AgentActionType, ChatPromptTemplate] = {
    "ANSWER_DIRECT_QUESTION": PROMPT_ANSWER_DIRECT_QUESTION,
    "ASK_SPIN_QUESTION": PROMPT_ASK_SPIN_QUESTION,
    "GENERATE_REBUTTAL": PROMPT_GENERATE_REBUTTAL,
    "ASK_CLARIFYING_QUESTION": PROMPT_ASK_CLARIFYING_QUESTION,
    "ACKNOWLEDGE_AND_TRANSITION": PROMPT_ACKNOWLEDGE_AND_TRANSITION,
    "PRESENT_SOLUTION_OFFER": PROMPT_PRESENT_SOLUTION_OFFER,
    "INITIATE_CLOSING": PROMPT_INITIATE_CLOSING,
    "CONFIRM_ORDER_DETAILS": PROMPT_CONFIRM_ORDER_DETAILS,
    "PROCESS_ORDER_CONFIRMATION": PROMPT_PROCESS_ORDER_CONFIRMATION,
    "HANDLE_CLOSING_CORRECTION": PROMPT_HANDLE_CLOSING_CORRECTION,
    "GENERATE_FAREWELL": PROMPT_GENERATE_FAREWELL,
}


# --- Função Auxiliar para Preparar Contexto Comum ---
def _prepare_common_prompt_context(state: RichConversationState) -> Dict[str, Any]:
    """
    Prepares common context variables needed by most generator prompts.

    Extracts information like company profile details (name, tone, language,
    offerings, fallback info), recent chat history, and RAG context from the
    current state to be used in various LLM prompts.

    Args:
        state: The current conversation state dictionary.

    Returns:
        A dictionary containing common context variables like 'company_name',
        'language', 'sales_tone', 'chat_history', 'rag_context', etc.
    """
    profile_dict = state.get("company_profile", {})
    # Use model_validate for Pydantic models if available and needed
    profile = (
        CompanyProfileSchema.model_validate(profile_dict)
        if profile_dict and hasattr(CompanyProfileSchema, "model_validate")
        else profile_dict
    )

    messages = state.get("messages", [])
    chat_history = _format_recent_chat_history(messages)
    last_user_message = (
        messages[-1].content if messages and messages[-1].type == "human" else "N/A"
    )

    # Safely access profile attributes using .get() for dictionaries
    company_name = profile.get("company_name", "nossa empresa")
    language = profile.get("language", "pt-br")
    sales_tone = profile.get("sales_tone", "profissional")
    business_description = profile.get("business_description", "N/A")
    offerings = profile.get("offering_overview", []) or []
    key_selling_points_list = profile.get("key_selling_points", []) or []
    communication_guidelines_list = profile.get("communication_guidelines", []) or []
    address = profile.get("address")
    opening_hours = profile.get("opening_hours")
    fallback_contact_info = profile.get(
        "fallback_contact_info", "Desculpe, não tenho essa informação no momento."
    )

    offering_summary = (
        "\n".join(
            [f"- {o.get('name')}: {o.get('short_description')}" for o in offerings]
        )
        if offerings
        else "N/A"
    )
    key_points = (
        "\n".join([f"- {p}" for p in key_selling_points_list])
        if key_selling_points_list
        else "N/A"
    )
    communication_guidelines = (
        "\n".join(communication_guidelines_list)
        if communication_guidelines_list
        else "N/A"
    )
    company_address_info = f"Endereço: {address}" if address else ""
    opening_hours_info = f"Horário: {opening_hours}" if opening_hours else ""

    return {
        "company_name": company_name,
        "language": language,
        "sales_tone": sales_tone,
        "business_description": business_description,
        "offering_summary": offering_summary,
        "key_selling_points": key_points,
        "company_address_info": company_address_info,
        "opening_hours_info": opening_hours_info,
        "communication_guidelines": communication_guidelines,
        "fallback_text": fallback_contact_info,
        "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
        "chat_history": chat_history,
        "last_user_message": last_user_message,
        "rag_context": state.get("retrieved_knowledge_for_next_action")
        or "Nenhum contexto adicional disponível.",
    }


# --- Função Auxiliar para Chamada LLM ---
async def _call_llm_for_generation(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    prompt_values: Dict[str, Any],
    node_name_for_logging: str,
) -> Optional[str]:
    """
    Invokes the LLM chain to generate text based on a prompt and values.

    Args:
        llm: The language model instance to use for generation.
        prompt: The ChatPromptTemplate defining the prompt structure.
        prompt_values: A dictionary containing values to fill the prompt template.
        node_name_for_logging: A string identifier for logging purposes.

    Returns:
        The generated text as a string, or None if generation fails or
        returns an empty string.
    """
    try:
        # Simple chain: prompt -> LLM -> String Output Parser
        chain = prompt | llm | StrOutputParser()
        logger.debug(f"[{node_name_for_logging}] Invoking LLM generation chain...")
        # logger.trace(f"[{node_name_for_logging}] Prompt Values: {json.dumps(prompt_values, indent=2, default=str)}") # Optional detailed logging

        generated_text = await chain.ainvoke(prompt_values)
        generated_text = generated_text.strip() if generated_text else ""

        if not generated_text:
            logger.warning(f"[{node_name_for_logging}] LLM returned empty string.")
            return None

        return generated_text
    except Exception as e:
        logger.exception(
            f"[{node_name_for_logging}] Error invoking LLM generation chain: {e}"
        )
        return None


# --- Nó Principal do Gerador de Resposta ---
async def response_generator_node(
    state: RichConversationState, config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generates the agent's text response based on the planned action command.

    This node selects the appropriate prompt based on the 'next_agent_action_command'
    and 'action_parameters' from the state, prepares the full context (common
    and action-specific), invokes the primary language model, and returns the
    generated text. It handles potential errors during context preparation or
    LLM invocation by returning a fallback message and logging errors.

    Args:
        state: The current conversation state dictionary.
        config: The graph configuration dictionary, expected to contain the
                'llm_primary_instance' under the 'configurable' key.

    Returns:
        A dictionary containing the generated text under the key
        'last_agent_generation_text', or None if no action was planned.
        Includes 'last_processing_error' if an error occurred.
    """
    node_name = "response_generator_node"
    logger.info(
        f"--- Starting Node: {node_name} (Turn: {state.get('current_turn_number', 0)}) ---"
    )

    llm_primary: Optional[BaseChatModel] = config.get("configurable", {}).get(
        "llm_primary_instance"
    )
    action_command: Optional[AgentActionType] = state.get("next_agent_action_command")
    action_params: AgentActionDetails = state.get("action_parameters", {})

    # --- Validations ---
    if not llm_primary:
        logger.error(f"[{node_name}] llm_primary_instance not found in config.")
        return {
            "last_agent_generation_text": None,
            "last_processing_error": "LLM for response generation unavailable.",
        }
    if not action_command:
        logger.warning(
            f"[{node_name}] No action command planned. Skipping response generation."
        )
        return {"last_agent_generation_text": None}

    logger.info(
        f"[{node_name}] Generating response for action: {action_command} with params: {action_params}"
    )

    # --- Prepare Context ---
    try:
        common_context = _prepare_common_prompt_context(state)
    except Exception as e:
        logger.exception(f"[{node_name}] Error preparing common prompt context: {e}")
        return {
            "last_agent_generation_text": None,
            "last_processing_error": f"Context preparation failed: {e}",
        }

    # --- Select Prompt and Prepare Specific Values ---
    selected_prompt = ACTION_TO_PROMPT_MAP.get(action_command)
    specific_values: Dict[str, Any] = {}

    if not selected_prompt:
        logger.error(
            f"[{node_name}] No prompt defined in ACTION_TO_PROMPT_MAP for action: {action_command}"
        )
        fallback_text = common_context.get("fallback_text", "Não sei como proceder.")
        return {
            "last_agent_generation_text": fallback_text,
            "last_processing_error": f"No prompt for action {action_command}",
        }

    # Populate specific values based on the action command
    try:
        if action_command == "ANSWER_DIRECT_QUESTION":
            specific_values["question_to_answer"] = action_params.get(
                "question_to_answer_text", "[Pergunta não especificada]"
            )
        elif action_command == "ASK_SPIN_QUESTION":
            specific_values["spin_type"] = action_params.get("spin_type", "Situation")
        elif action_command == "GENERATE_REBUTTAL":
            specific_values["objection_text"] = action_params.get(
                "objection_text_to_address", "[Objeção não especificada]"
            )
        elif action_command == "ASK_CLARIFYING_QUESTION":
            vague_text = (
                state.get("current_agent_goal", {})
                .get("goal_details", {})
                .get("text", "[Declaração vaga não especificada]")
            )
            specific_values["vague_statement_text"] = vague_text
        elif action_command == "ACKNOWLEDGE_AND_TRANSITION":
            specific_values["off_topic_text"] = action_params.get(
                "off_topic_text", "[comentário anterior]"
            )
            specific_values["previous_goal_topic"] = action_params.get(
                "previous_goal_topic", "o assunto anterior"
            )
        elif action_command == "PRESENT_SOLUTION_OFFER":
            # Note: Prompt already selected by map
            specific_values["product_name_to_present"] = action_params.get(
                "product_name_to_present", "[Produto não especificado]"
            )
            specific_values["key_benefit_to_highlight"] = action_params.get(
                "key_benefit_to_highlight", "[Benefício não especificado]"
            )
        elif action_command == "INITIATE_CLOSING":
            product_name = action_params.get("product_name")
            price = action_params.get("price")
            product_info = ""
            product_fallback = "este pedido"
            if product_name:
                product_info += f"o *{product_name}*"
                product_fallback = f"o *{product_name}*"
                if price is not None:
                    try:
                        product_info += f" (R${price:.2f})"
                    except (TypeError, ValueError):
                        logger.warning(
                            f"Could not format price for INITIATE_CLOSING: {price}"
                        )
            else:
                product_info = "este pedido"
            specific_values["product_name_price_info"] = product_info
            specific_values["product_name_fallback"] = product_fallback
        elif action_command == "CONFIRM_ORDER_DETAILS":
            product_name = action_params.get("product_name", "o produto selecionado")
            price = action_params.get("price")
            price_info_suffix = action_params.get("price_info", "")
            price_str = "valor combinado"
            if price is not None:
                try:
                    price_str = f"R${price:.2f}{price_info_suffix}"
                except (TypeError, ValueError):
                    logger.warning(
                        f"Could not format price for CONFIRM_ORDER_DETAILS: {price}"
                    )
                    price_str = "valor informado"
            specific_values["product_name"] = product_name
            specific_values["price_info"] = price_str
        elif action_command == "PROCESS_ORDER_CONFIRMATION":
            specific_values["product_name"] = action_params.get(
                "product_name", "seu pedido"
            )
        elif action_command == "HANDLE_CLOSING_CORRECTION":
            specific_values["context"] = action_params.get(
                "context", "Estávamos finalizando seu pedido."
            )
        elif action_command == "GENERATE_FAREWELL":
            specific_values["reason"] = action_params.get(
                "reason", "concluindo a conversa"
            )
            specific_values["fallback_contact_info"] = common_context.get(
                "fallback_text", ""
            )

    except (
        Exception
    ) as e:  # Catch potential errors during parameter extraction/formatting
        logger.exception(
            f"[{node_name}] Error preparing specific values for action {action_command}: {e}"
        )
        fallback_text = common_context.get(
            "fallback_text", "Erro ao preparar a resposta."
        )
        return {
            "last_agent_generation_text": fallback_text,
            "last_processing_error": f"Data preparation error for action {action_command}: {e}",
        }

    # --- Invoke LLM ---
    prompt_values = {**common_context, **specific_values}
    generated_text = await _call_llm_for_generation(
        llm=llm_primary,
        prompt=selected_prompt,
        prompt_values=prompt_values,
        node_name_for_logging=f"{node_name}:{action_command}",
    )

    if generated_text is None:
        # Use fallback if generation failed or returned empty
        generated_text = common_context.get(
            "fallback_text", "Não consegui gerar uma resposta no momento."
        )
        logger.warning(
            f"[{node_name}] LLM generation failed or returned empty for {action_command}. Using fallback."
        )
        error_msg = f"LLM generation failed or empty for {action_command}"
        return {
            "last_agent_generation_text": generated_text,
            "last_processing_error": error_msg,  # Report the error
        }

    logger.info(
        f"[{node_name}] Generated response text (Action: {action_command}): '{generated_text[:100]}...'"
    )

    # Return the generated text to be used by the next node
    return {
        "last_agent_generation_text": generated_text,
        "last_processing_error": None,  # Clear previous errors on success
    }
