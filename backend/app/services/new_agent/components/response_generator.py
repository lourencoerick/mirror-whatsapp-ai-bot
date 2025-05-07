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


# --- Mapeamento de Ação para Prompt ---
ACTION_TO_PROMPT_MAP: Dict[AgentActionType, ChatPromptTemplate] = {
    "ANSWER_DIRECT_QUESTION": PROMPT_ANSWER_DIRECT_QUESTION,
    "ASK_SPIN_QUESTION": PROMPT_ASK_SPIN_QUESTION,
    "GENERATE_REBUTTAL": PROMPT_GENERATE_REBUTTAL,
    "ASK_CLARIFYING_QUESTION": PROMPT_ASK_CLARIFYING_QUESTION,
    "ACKNOWLEDGE_AND_TRANSITION": PROMPT_ACKNOWLEDGE_AND_TRANSITION,
    "PRESENT_SOLUTION_OFFER": PROMPT_PRESENT_SOLUTION_OFFER,
    # Adicionar outros mapeamentos aqui quando os prompts forem criados
    # "INITIATE_CLOSING": PROMPT_INITIATE_CLOSING,
    # ... etc
}


# --- Função Auxiliar para Preparar Contexto Comum ---
# (Definida anteriormente, pode ser movida para utils)
def _prepare_common_prompt_context(state: RichConversationState) -> Dict[str, Any]:
    """Prepares common context variables needed by most generator prompts."""
    profile_dict = state.get("company_profile", {})
    profile = (
        CompanyProfileSchema.model_validate(profile_dict)
        if profile_dict
        else CompanyProfileSchema()
    )
    messages = state.get("messages", [])
    chat_history = _format_recent_chat_history(messages)
    last_user_message = (
        messages[-1].content if messages and messages[-1].type == "human" else "N/A"
    )
    offerings = getattr(profile, "offering_overview", []) or []
    offering_summary = (
        "\n".join([f"- {o.name}: {o.short_description}" for o in offerings]) or "N/A"
    )
    key_points = (
        "\n".join([f"- {p}" for p in getattr(profile, "key_selling_points", [])])
        if getattr(profile, "key_selling_points", [])
        else "N/A"
    )

    return {
        "company_name": getattr(profile, "company_name", "nossa empresa"),
        "language": getattr(profile, "language", "pt-br"),
        "sales_tone": getattr(profile, "sales_tone", "profissional"),
        "business_description": getattr(profile, "business_description", "N/A"),
        "offering_summary": offering_summary,
        "key_selling_points": key_points,
        "company_address_info": (
            f"Endereço: {profile.address}" if getattr(profile, "address", None) else ""
        ),
        "opening_hours_info": (
            f"Horário: {profile.opening_hours}"
            if getattr(profile, "opening_hours", None)
            else ""
        ),
        "communication_guidelines": (
            "\n".join(getattr(profile, "communication_guidelines", []))
            if getattr(profile, "communication_guidelines", [])
            else "N/A"
        ),
        "fallback_text": getattr(
            profile,
            "fallback_contact_info",
            "Desculpe, não tenho essa informação no momento.",
        ),
        "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
        "chat_history": chat_history,
        "last_user_message": last_user_message,
        "rag_context": state.get("retrieved_knowledge_for_next_action")
        or "Nenhum contexto adicional disponível.",
    }


# --- Função Auxiliar para Chamada LLM (Pode ir para utils) ---
async def _call_llm_for_generation(
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
    prompt_values: Dict[str, Any],
    node_name_for_logging: str,
) -> Optional[str]:
    """Helper function to invoke LLM chain for text generation."""
    try:
        chain = prompt | llm | StrOutputParser()
        logger.debug(f"[{node_name_for_logging}] Invoking LLM generation chain...")
        # logger.trace(f"[{node_name_for_logging}] Prompt Values: {json.dumps(prompt_values, indent=2, default=str)}")

        generated_text = await chain.ainvoke(prompt_values)
        generated_text = generated_text.strip()

        if not generated_text:
            logger.warning(f"[{node_name_for_logging}] LLM returned empty string.")
            return None  # Retornar None para indicar falha ou vazio

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
    LangGraph node that generates the agent's text response based on the planned action.
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

    # --- Validações ---
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
        return {"last_agent_generation_text": None}  # Não é um erro, apenas skip

    logger.info(
        f"[{node_name}] Generating response for action: {action_command} with params: {action_params}"
    )

    # --- Preparar Contexto Comum ---
    try:
        common_context = _prepare_common_prompt_context(state)
    except Exception as e:
        logger.exception(f"[{node_name}] Error preparing common prompt context: {e}")
        return {
            "last_agent_generation_text": None,
            "last_processing_error": f"Context preparation failed: {e}",
        }

    # --- Selecionar Prompt e Preparar Valores Específicos ---
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

    # Preencher valores específicos baseado na ação
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
            # Tentar pegar o texto vago do goal_details associado a esta ação
            # Assumindo que o Planner colocou o texto vago no goal_details quando definiu o goal CLARIFYING_USER_INPUT
            vague_text = (
                state.get("current_agent_goal", {})
                .get("goal_details", {})
                .get("text", "[Declaração vaga não especificada]")
            )
            specific_values["vague_statement_text"] = vague_text
        elif action_command == "ACKNOWLEDGE_AND_TRANSITION":
            off_topic_text = (
                state.get("current_agent_goal", {})
                .get("goal_details", {})
                .get("text", "[Comentário off-topic não especificado]")
            )
            previous_goal = state.get("current_agent_goal", {}).get(
                "previous_goal_if_interrupted", {}
            )
            # Tentar extrair um tópico do objetivo anterior para a transição
            # (Isso pode precisar de mais inteligência ou uma estrutura melhor no goal_details)
            previous_goal_topic = previous_goal.get("goal_details", {}).get(
                "topic", "o assunto anterior"
            )
            specific_values["off_topic_text"] = off_topic_text
            specific_values["previous_goal_topic"] = previous_goal_topic

        elif action_command == "PRESENT_SOLUTION_OFFER":
            selected_prompt = PROMPT_PRESENT_SOLUTION_OFFER
            specific_values["product_name_to_present"] = action_params.get(
                "product_name_to_present", "[Produto não especificado]"
            )
            specific_values["key_benefit_to_highlight"] = action_params.get(
                "key_benefit_to_highlight", "[Benefício não especificado]"
            )
            # Adicionar outros casos aqui...

    except KeyError as e:
        logger.error(
            f"[{node_name}] Missing expected key in action_parameters or goal_details for action {action_command}: {e}"
        )
        fallback_text = common_context.get(
            "fallback_text", "Erro ao preparar a resposta."
        )
        return {
            "last_agent_generation_text": fallback_text,
            "last_processing_error": f"Missing data for action {action_command}: {e}",
        }

    # --- Invocar LLM ---
    prompt_values = {**common_context, **specific_values}
    generated_text = await _call_llm_for_generation(
        llm=llm_primary,
        prompt=selected_prompt,
        prompt_values=prompt_values,
        node_name_for_logging=f"{node_name}:{action_command}",  # Log mais específico
    )

    if generated_text is None:
        # Usar fallback se a geração falhou ou retornou vazio
        generated_text = common_context.get(
            "fallback_text", "Não consegui gerar uma resposta no momento."
        )
        logger.warning(
            f"[{node_name}] LLM generation failed or returned empty for {action_command}. Using fallback."
        )
        # Manter o erro no estado se a chamada LLM falhou? Ou apenas usar fallback?
        # Vamos usar fallback mas limpar o erro por enquanto, assumindo que o fallback é aceitável.
        error_msg = f"LLM generation failed or empty for {action_command}"
        # Retornar o fallback e o erro
        return {
            "last_agent_generation_text": generated_text,
            "last_processing_error": error_msg,
        }

    logger.info(
        f"[{node_name}] Generated response text (Action: {action_command}): '{generated_text[:100]}...'"
    )

    # Retornar o texto gerado. O próximo nó (StateUpdater final ou OutputFormatter) o usará.
    return {
        "last_agent_generation_text": generated_text,
        "last_processing_error": None,  # Limpar erro se a geração foi bem-sucedida
    }
