# backend/app/services/ai_reply/new_agent/components/response_generator.py

from typing import Dict, List, Optional, Any
from loguru import logger
import json
from datetime import datetime
import pytz

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
    CustomerQuestionStatusType,
    ProposedSolution,
)

# Importar utils de prompt
from ..prompt_utils import WHATSAPP_MARKDOWN_INSTRUCTIONS
from app.api.schemas.company_profile import CompanyProfileSchema, OfferingInfo

# Importar função auxiliar de formatação de histórico
try:
    from .input_processor import _format_recent_chat_history
except ImportError:  # Fallback se a estrutura mudar

    def _format_recent_chat_history(*args, **kwargs) -> str:
        return "Histórico indisponível."


# --- Prompts ---

PROMPT_GENERATE_GREETING = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é o Assistente de Vendas IA inicial da '{company_name}'.
Sua tarefa é gerar uma mensagem de saudação curta, amigável e profissional para iniciar a conversa com o cliente.
Use o tom de vendas '{sales_tone}' e o idioma '{language}'.
Apresente-se brevemente e pergunte como pode ajudar o cliente hoje.
Mantenha a mensagem concisa.
Aplique formatação WhatsApp sutil: {formatting_instructions}

Exemplo: "Olá! Sou o assistente virtual da *{company_name}*. Como posso te ajudar hoje?"
         "Oi! Bem-vindo(a) à *{company_name}*. Em que posso ser útil?"

Gere APENAS a mensagem de saudação.""",
        ),
    ]
)

PROMPT_ANSWER_DIRECT_QUESTION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA para '{company_name}'.
Seu objetivo é responder à pergunta específica do cliente de forma precisa e completa, usando o 'Contexto Relevante' (se disponível) e o 'Perfil da Empresa'.
Comunique-se em {language} com um tom {sales_tone}. A hora atual é {current_datetime}.

**Pergunta Específica do Cliente:**
{question_to_answer}

**Contexto Relevante (RAG - Use se ajudar a responder):**
{rag_context}
--- Fim do Contexto Relevante ---

**Informações do Perfil da Empresa (Use se RAG não for suficiente):**
Descrição: {business_description}
Ofertas: {offering_summary}
{company_address_info}
{opening_hours_info}

Opções de Entrega/Retirada:
{delivery_options_info}

Diretrizes: {communication_guidelines}

--- Fim das Informações do Perfil ---

**Instruções Cruciais:**
1.  **Priorize o Contexto RAG:** Baseie sua resposta PRIMEIRO no 'Contexto Relevante (RAG)', se ele contiver a informação necessária para responder DIRETAMENTE à pergunta.
2.  **Use o Perfil da Empresa:** Se o RAG não for suficiente ou relevante, use as 'Informações do Perfil da Empresa'.
3.  **Seja Honesto:** Se a informação não estiver no RAG nem no Perfil, use o texto de fallback: '{fallback_text}'. NÃO invente informações (preços, características, prazos, etc.).
4.  **Foco na Pergunta:** Responda direta e exclusivamente à '{question_to_answer}'. NÃO adicione perguntas de acompanhamento (como 'Isso ajudou?', 'Posso ajudar com algo mais?') nem frases de encerramento genéricas. Termine a resposta logo após fornecer a informação.
5.  **Use o Histórico:** Consulte o 'Histórico Recente' abaixo para entender o contexto da conversa.
6.  **Formatação:** Aplique a formatação WhatsApp ({formatting_instructions}) de forma clara e útil.
{repetition_context_instructions}

HISTÓRICO RECENTE (Contexto da Conversa):
{chat_history}
--- Fim do Histórico ---

Responda APENAS à pergunta específica do cliente: '{question_to_answer}'.""",
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

Use o contexto, caso esteja disponível, para te ajudar a formular uma pergunta mais personalizada: "{last_action_context}"

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
            """Você é um Assistente de Vendas IA da '{company_name}'.
O cliente acaba de confirmar o pedido do '{product_name}'.
Sua tarefa é:
1. Agradecer ao cliente pela confiança e pela compra do *{product_name}*.
2. Confirmar que o pedido foi recebido/processado com sucesso.
3. Fornecer o link para que o cliente possa prosseguir com o pagamento ou finalizar a compra.
4. Manter a mensagem positiva, concisa e clara.

**Contexto:**
- Tom de Vendas: {sales_tone}
- Idioma: {language}
- Produto Confirmado: *{product_name}*
- Link para Pagamento/Finalização: {product_link_or_fallback} 
  (Este link DEVE ser o destino para o cliente completar a compra. Se for um link geral do site, adapte a chamada para ação.)

**Instruções Específicas:**
- **Agradecimento e Confirmação:** Comece com um agradecimento caloroso e confirme o pedido. Ex: "Excelente! Seu pedido do *{product_name}* foi confirmado com sucesso. Agradecemos muito pela sua confiança!"
- **Chamada para Ação com Link:**
    - Se `{product_link_or_fallback}` parecer um link direto de produto/checkout (ex: contendo o nome do produto ou palavras como 'checkout', 'pagamento', 'carrinho'):
      "Para finalizar sua compra e efetuar o pagamento, por favor, acesse o link: {product_link_or_fallback}"
    - Se `{product_link_or_fallback}` parecer um link mais geral do site (ex: apenas o domínio principal):
      "Você pode completar seu pedido e prosseguir para o pagamento através do nosso site: {product_link_or_fallback}"
    - **Importante:** Apresente o link de forma clara.
- **Próximos Passos (Mínimo):** A menos que haja um próximo passo MUITO específico e crucial que NÃO seja o link (o que é raro neste momento), não adicione informações sobre "nossa equipe entrará em contato" ou "aguarde X". O foco é levar o cliente ao link. Se o link é tudo, termine após fornecer o link e talvez um "Até breve!" ou "Qualquer dúvida no processo, é só chamar!".
- **Formatação:** Use formatação WhatsApp sutil e eficaz ({formatting_instructions}).

HISTÓRICO RECENTE (para seu contexto):
{chat_history}
--- Fim do Histórico ---

Gere APENAS a mensagem de confirmação do pedido e o link para finalização da compra do *{product_name}*.""",
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

PROMPT_SEND_FOLLOW_UP_MESSAGE = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas da '{company_name}'. O usuário não respondeu à sua última mensagem por um tempo.
Sua tarefa é enviar uma mensagem de follow-up gentil para tentar reengajar o cliente.

**Contexto da Conversa:**
- Última mensagem enviada pelo agente (você): "{last_agent_action_text_for_follow_up}"
- Goal que o agente estava perseguindo antes da pausa: {goal_type_before_pause}
- Esta é a tentativa de follow-up número: {current_follow_up_attempts_display} (de um total de {max_follow_up_attempts_total} tentativas).
- Idioma: {language}
- Tom de Vendas: {sales_tone} (use um tom ainda mais suave e compreensivo para follow-up)

**Instruções para a Mensagem de Follow-up:**
1.  **Reconheça a Pausa:** Comece de forma suave, ex: "Olá novamente!", "Só para checar...", "Notei que nossa conversa pausou...".
2.  **Referencie o Contexto:** Mencione brevemente o tópico da sua última mensagem ou o objetivo da conversa para ajudar o cliente a se lembrar. (Use `{last_agent_action_text_for_follow_up}` e `{goal_type_before_pause}` como referência).
3.  **Seja Convidativo, Não Insistente:**
    *   **Primeiro Follow-up (tentativa 1 de {max_follow_up_attempts_total}):** "Gostaria de continuar de onde paramos sobre [tópico] ou talvez precise de mais um momento para pensar?"
    *   **Follow-ups Intermediários:** "Só para checar se você teve chance de pensar sobre [tópico]. Alguma dúvida ou algo mais em que posso ajudar neste momento?"
    *   **Último Follow-up (tentativa {max_follow_up_attempts_total} de {max_follow_up_attempts_total}):** "Ainda estou à disposição se precisar de algo referente a [tópico]. Caso contrário, sem problemas e agradeço seu tempo até aqui!" (Não faça uma pergunta se for a última tentativa antes de um possível farewell automático).
4.  **Mantenha Curto e Amigável.**
5.  **Formatação:** Aplique formatação WhatsApp sutil: {formatting_instructions}

HISTÓRICO RECENTE (para seu contexto, não necessariamente para repetir ao usuário):
{chat_history}

Gere APENAS a mensagem de follow-up.""",
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
    "PROCESS_ORDER_CONFIRMATION": PROMPT_PROCESS_ORDER_CONFIRMATION,  # <<< ADDED
    "HANDLE_CLOSING_CORRECTION": PROMPT_HANDLE_CLOSING_CORRECTION,
    "GENERATE_FAREWELL": PROMPT_GENERATE_FAREWELL,  #
    "GENERATE_GREETING": PROMPT_GENERATE_GREETING,
    "SEND_FOLLOW_UP_MESSAGE": PROMPT_SEND_FOLLOW_UP_MESSAGE,
    # ... etc
}


def _format_list_items(items: List[str], prefix: str = "- ") -> str:
    """Formats list items with a prefix and newline separators for the prompt."""
    if not items:
        return "N/A"
    return "\n".join([f"{prefix}{item}" for item in items])


def _format_offerings(offerings: List[OfferingInfo]) -> str:
    """Formats the list of offerings, including the link if available."""
    if not offerings:
        return "No specific offerings listed."
    lines = []
    for offer in offerings:
        features = ", ".join(offer.key_features) if offer.key_features else "N/A"
        price = offer.price_info if offer.price_info else "N/A"
        link_info = f", Link: {offer.link}" if offer.link else ""
        bonus_items = _format_list_items(offer.bonus_items) or "N/A"
        lines.append(
            f"- {offer.name}: {offer.short_description} (Features: {features},\nPreço: {price}{link_info}\nBônus Items:{bonus_items})"
        )
    return "\n".join(lines)


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
    offering_summary = _format_offerings(offerings) or "N/A"

    key_selling_points = getattr(profile, "key_selling_points", [])
    key_points = _format_list_items(key_selling_points) or "N/A"

    delivery_options_info = (
        (
            _format_list_items(profile.delivery_options)
            if profile.delivery_options
            else "Opções de delivery/pickup não especificadas."
        ),
    )
    brasilia_tz = pytz.timezone("America/Sao_Paulo")
    current_time_str = datetime.now(brasilia_tz).strftime("%Y-%m-%d %H:%M:%S %Z")

    return {
        "company_name": getattr(profile, "company_name", "nossa empresa"),
        "language": getattr(profile, "language", "pt-br"),
        "sales_tone": getattr(profile, "sales_tone", "profissional"),
        "business_description": getattr(profile, "business_description", "N/A"),
        "offering_summary": offering_summary,
        "key_selling_points": key_points,
        "delivery_options_info": delivery_options_info,
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
        "fallback_text": getattr(profile, "fallback_contact_info", None)
        or "Desculpe, não tenho essa informação no momento.",
        "formatting_instructions": WHATSAPP_MARKDOWN_INSTRUCTIONS,
        "chat_history": chat_history,
        "last_user_message": last_user_message,
        "rag_context": state.get("retrieved_knowledge_for_next_action")
        or "Nenhum contexto adicional disponível.",
        "current_datetime": current_time_str,
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
            question_status: Optional[CustomerQuestionStatusType] = action_params.get("question_to_answer_status")  # type: ignore
            repetition_instructions = ""
            if question_status == "repetition_after_fallback":
                repetition_instructions = (
                    "\n6. **Instrução Adicional:** Esta pergunta é uma repetição de uma anterior que você não conseguiu responder "
                    "com informações específicas (usou fallback). **NÃO repita o fallback**. Reconheça que já foi perguntado, "
                    "peça desculpas por ainda não ter a informação e ofereça ajuda alternativa (verificar com equipe, "
                    "oferecer outra informação, etc.)."
                )
            elif question_status == "repetition_after_satisfactory_answer":
                repetition_instructions = (
                    "\n6. **Instrução Adicional:** Esta pergunta é uma repetição de uma anterior que você já respondeu "
                    "satisfatoriamente. Reitere a resposta anterior de forma concisa ou pergunte se o cliente tem alguma dúvida adicional sobre ela."
                )
            specific_values["repetition_context_instructions"] = repetition_instructions

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
            specific_values["last_action_context"] = action_params.get("context", "N/A")
        elif action_command == "ACKNOWLEDGE_AND_TRANSITION":

            specific_values["off_topic_text"] = action_params.get(
                "off_topic_text", "[comentário anterior]"
            )
            specific_values["previous_goal_topic"] = action_params.get(
                "previous_goal_topic", "o assunto anterior"
            )

        elif action_command == "PRESENT_SOLUTION_OFFER":
            selected_prompt = PROMPT_PRESENT_SOLUTION_OFFER
            specific_values["product_name_to_present"] = action_params.get(
                "product_name_to_present", "[Produto não especificado]"
            )
            specific_values["key_benefit_to_highlight"] = action_params.get(
                "key_benefit_to_highlight", "[Benefício não especificado]"
            )
            # Adicionar outros casos aqui..

        elif action_command == "INITIATE_CLOSING":
            product_name = action_params.get("product_name")
            price = action_params.get("price")
            product_info = ""
            product_fallback = "este pedido"
            if product_name:
                product_info += f"o *{product_name}*"
                product_fallback = f"o *{product_name}*"
                if price:
                    product_info += f" (R${price:.2f})"  # Basic price formatting
            else:
                product_info = "este pedido"

            specific_values["product_name_price_info"] = product_info
            specific_values["product_name_fallback"] = product_fallback

        elif action_command == "CONFIRM_ORDER_DETAILS":
            product_name = action_params.get("product_name", "o produto selecionado")
            price = action_params.get("price")
            price_info_suffix = action_params.get("price_info", "")  # e.g., "/mês"
            price_str = "valor combinado"
            if price is not None:
                try:
                    price_str = f"R${price:.2f}{price_info_suffix}"
                except (TypeError, ValueError):
                    logger.warning(
                        f"Could not format price for CONFIRM_ORDER_DETAILS: {price}"
                    )
                    price_str = "valor informado"  # Fallback if formatting fails

            specific_values["product_name"] = product_name
            specific_values["price_info"] = price_str

        elif action_command == "PROCESS_ORDER_CONFIRMATION":
            specific_values["product_name"] = action_params.get(
                "product_name", "seu pedido"
            )

            product_link = None
            active_proposal: Optional[ProposedSolution] = state.get("active_proposal")  # type: ignore
            if active_proposal and isinstance(
                active_proposal, dict
            ):  # Checar se é dict
                product_link = active_proposal.get("product_url")

            # Usar o link do produto se disponível, senão o fallback_text (que é o company_main_link_fallback)
            specific_values["product_link_or_fallback"] = (
                product_link
                or common_context.get("company_main_link_fallback", "nosso site.")
            )
            logger.debug(
                f"[{node_name}] For PROCESS_ORDER_CONFIRMATION, product_link_or_fallback set to: {specific_values['product_link_or_fallback']}"
            )

        elif action_command == "HANDLE_CLOSING_CORRECTION":
            specific_values["context"] = action_params.get(
                "context", "Estávamos finalizando seu pedido."
            )

        elif action_command == "GENERATE_FAREWELL":
            specific_values["reason"] = action_params.get(
                "reason", "concluindo a conversa"
            )
            # Pass fallback contact info from common context if needed by prompt
            specific_values["fallback_contact_info"] = common_context.get(
                "fallback_text", ""
            )
        elif action_command == "SEND_FOLLOW_UP_MESSAGE":
            # Obter a última ação real do agente (não DECIDE_PROACTIVE_STEP)
            # Isso pode ser um pouco complexo se a última ação foi o próprio DECIDE_PROACTIVE_STEP.
            # O Planner deveria ter passado o goal original ou a última mensagem do agente como parâmetro.
            # Por agora, vamos assumir que o `last_agent_action` no estado é a última mensagem *enviada*.
            last_action_obj = state.get("last_agent_action")
            last_agent_text_for_follow_up = "nossa conversa anterior"
            if (
                last_action_obj
                and isinstance(last_action_obj, dict)
                and last_action_obj.get("action_generation_text")
            ):
                last_agent_text_for_follow_up = last_action_obj.get(
                    "action_generation_text", last_agent_text_for_follow_up
                )

            current_goal_obj = state.get("current_agent_goal")
            goal_type_before_pause = "tópico anterior"
            if current_goal_obj and isinstance(current_goal_obj, dict):
                # Se o goal atual é o resultado de um `DECIDE_PROACTIVE_STEP` que foi acionado por um timeout,
                # o goal "real" que estava sendo perseguido antes da pausa está no `previous_goal_if_interrupted`
                # do goal que o Planner definiu quando o timeout foi detectado.
                # No entanto, o `proactive_step_decider_node` não muda o goal, ele apenas define a próxima ação.
                # Então, o `current_agent_goal` no estado deve ser o goal que estava ativo.
                goal_type_before_pause = current_goal_obj.get(
                    "goal_type", goal_type_before_pause
                )

            specific_values["last_agent_action_text_for_follow_up"] = (
                last_agent_text_for_follow_up
            )
            specific_values["goal_type_before_pause"] = goal_type_before_pause
            specific_values["current_follow_up_attempts_display"] = (
                action_params.get("current_follow_up_attempts", 0) + 1
            )  # Para display (1ª, 2ª)
            specific_values["current_follow_up_attempts"] = action_params.get(
                "current_follow_up_attempts", 0
            )  # Para lógica no prompt
            specific_values["max_follow_up_attempts_total"] = action_params.get(
                "max_follow_up_attempts_total", 2
            )  # Obter da config do agente se possível

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
