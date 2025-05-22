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

**Instrução Adicional Importante:**
*   Verifique o valor de '{combined_spin_question_type_for_prompt}'.
*   **SE '{combined_spin_question_type_for_prompt}' for 'Situation' (ou qualquer outro tipo SPIN válido):**
    Após a saudação, você DEVE adicionar uma pergunta aberta do tipo 'Situation' para entender o contexto inicial do cliente.
    Exemplos de pergunta Situation para combinar com a saudação:
    - "Para começarmos, poderia me contar um pouco sobre o que te traz aqui hoje ou qual desafio você está buscando resolver?"
    - "Para que eu possa te direcionar melhor, qual o seu principal objetivo ao entrar em contato conosco?"
*   **SE '{combined_spin_question_type_for_prompt}' for 'None' ou não for um tipo SPIN válido:**
    APENAS gere a mensagem de saudação padrão, perguntando como pode ajudar de forma geral.
    Exemplo de saudação padrão: "Olá! Sou o assistente virtual da *{company_name}*. Como posso te ajudar hoje?"

**Instruções Gerais:**
*   Use o tom de vendas '{sales_tone}' e o idioma '{language}'.
*   Mantenha a mensagem concisa, mesmo que combinada.
*   Aplique formatação WhatsApp sutil: {formatting_instructions}

Gere APENAS a mensagem de saudação (pura ou combinada com a pergunta Situation, conforme instruído).""",
        ),
    ]
)

PROMPT_ANSWER_DIRECT_QUESTION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA para '{company_name}'.
Seu objetivo é responder à pergunta específica do cliente de forma precisa e completa, usando o 'Contexto Relevante' (se disponível) e o 'Perfil da Empresa'. OPCIONALMENTE, se instruído com um 'Tipo de Pergunta SPIN Combinada', você DEVE adicionar essa pergunta SPIN APÓS sua resposta principal, de forma fluida.

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
3.  **Seja Honesto sobre Limites de Conhecimento:**
    *   Se a informação para responder COMPLETAMENTE à '{question_to_answer}' NÃO estiver no RAG nem no Perfil da Empresa, use EXATAMENTE o seguinte texto de fallback: '{fallback_text}'.
    *   NÃO invente informações (preços, características, prazos, etc.).
4.  **Resposta Direta e Conclusiva:**
       a.  Responda direta e exclusivamente à '{question_to_answer}' usando as informações encontradas (RAG ou Perfil).
       b.  **Se você conseguiu encontrar informações e acredita que respondeu à pergunta satisfatoriamente com o conhecimento disponível, TERMINE SUA RESPOSTA IMEDIATAMENTE APÓS FORNECER ESSA INFORMAÇÃO, caso '{combined_spin_question_type_for_prompt}' seja 'None'.**
       c.  **NÃO adicione frases como "Para mais detalhes, visite nosso site", "Entre em contato conosco", ou qualquer outra forma de direcionar o cliente para outro canal SE você já forneceu uma resposta baseada no seu conhecimento.** A exceção é se a própria informação recuperada (RAG/Perfil) explicitamente instruir a fornecer um link específico como parte da resposta direta àquela pergunta.
       d.  NÃO adicione perguntas de acompanhamento genéricas (como 'Isso ajudou?', 'Posso ajudar com algo mais?') ou frases de encerramento genéricas.
5.  **Use o Histórico:** Consulte o 'Histórico Recente' abaixo para entender o contexto da conversa.

6. **Instruções para a PERGUNTA SPIN COMBINADA (SE '{combined_spin_question_type_for_prompt}' for fornecido e não for 'None'):**
*   Após fornecer a resposta principal à pergunta do cliente, adicione uma pergunta aberta do tipo SPIN: '{combined_spin_question_type_for_prompt}'.
*   Faça a transição de forma natural. Ex: "Respondido isso, para entender melhor suas necessidades, [pergunta SPIN do tipo {combined_spin_question_type_for_prompt}]?"
*   A pergunta SPIN deve ser relevante para o contexto geral da conversa e para o tipo '{combined_spin_question_type_for_prompt}'.
    *   'Situation': Entender o contexto atual do cliente.
    *   'Problem': Descobrir dores ou insatisfações.
    *   'Implication': Explorar as consequências dos problemas.
    *   'NeedPayoff': Focar nos benefícios de resolver o problema.

7.  **Formatação:** Aplique a formatação WhatsApp ({formatting_instructions}) de forma clara e útil.
{repetition_context_instructions}


HISTÓRICO RECENTE (Contexto da Conversa):
{chat_history}
--- Fim do Histórico ---

Responda APENAS à pergunta específica do cliente: '{question_to_answer}' e, se aplicável, adicione a pergunta SPIN combinada.
Combine tudo em UMA ÚNICA mensagem.""",
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
            """Você é um Assistente de Vendas IA empático e prestativo da '{company_name}'.

Sua tarefa é fazer UMA única pergunta aberta e clara para obter o esclarecimento necessário do cliente.
Mantenha um tom {sales_tone} e use o idioma {language}.
CONTEXTO PARA SUA PERGUNTA (fornecido pelo sistema de planejamento):
{clarification_context_from_planner}

Instruções:
Use o Contexto: Baseie sua pergunta diretamente no 'CONTEXTO PARA SUA PERGUNTA' fornecido. Este contexto explica por que a clarificação é necessária e pode já conter uma sugestão de pergunta.
Se o contexto já contiver uma pergunta clara (ex: nos casos de "product_or_need_for_purchase"), use essa pergunta ou uma variação muito próxima e natural.
Se o contexto for uma declaração vaga do usuário (ex: "Não sei bem...", que estará em {clarification_context_from_planner}): Sua pergunta deve tentar fazer o cliente elaborar sobre essa declaração. Exemplos: "Para que eu possa te ajudar melhor, poderia me dizer um pouco mais sobre o que está pensando em relação a isso?", "Pode elaborar um pouco mais sobre essa dúvida?".
Clareza e Concisão: A pergunta deve ser fácil de entender e ir direto ao ponto.
Formato WhatsApp: Use formatação WhatsApp sutil ({formatting_instructions}).
HISTÓRICO RECENTE (para seu contexto geral da conversa):
{chat_history}
Gere APENAS a pergunta clarificadora com base no 'CONTEXTO PARA SUA PERGUNTA'.""",
        ),
    ]
)

PROMPT_ACKNOWLEDGE_AND_TRANSITION = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA da '{company_name}', mestre em conduzir conversas de forma natural e produtiva.
O cliente fez um comentário que parece desviar do fluxo principal da conversa:
Cliente: "{off_topic_text}"

Seu objetivo é:
1.  **Reconhecer Brevemente com Naturalidade:** Valide o comentário do cliente de forma curta, empática e que soe humana.
    Exemplos: "Entendi.", "Interessante observação!", "Anotado.", "Hehe, boa!", "Certo."
    Evite ser excessivamente formal ou robótico no reconhecimento.

2.  **Analisar o Histórico Recente (Mentalmente):** Revise o "HISTÓRICO RECENTE DA CONVERSA" abaixo, especialmente as últimas 2-3 trocas ANTES do comentário "{off_topic_text}".

3.  **Decidir a Melhor Transição:**
    *   **Cenário A (Ponto de Retorno Claro):** Se o AGENTE (você) fez uma pergunta clara ou estava no meio de uma explicação específica antes do desvio, tente retomar esse ponto diretamente, mas de forma suave.
        Exemplo (Agente perguntou sobre desafios, cliente falou do pão de queijo):
        Cliente: "O pão de queijo aqui perto está um absurdo de caro!"
        Você: "Hehe, entendo a questão do pão de queijo! Mas voltando aos desafios que você mencionou sobre [desafio específico], poderia me contar mais?"

    *   **Cenário B (Contexto Menos Definido ou Início de Conversa):** Se o desvio ocorreu muito no início, ou se o "assunto anterior" era muito geral (como uma saudação), ou se o ponto de retorno não é óbvio, faça uma transição mais aberta e convidativa para (re)engajar o cliente no propósito da conversa com a '{company_name}'.
        Exemplo (Cliente comenta algo aleatório após a saudação inicial do agente):
        Cliente: "Hoje o trânsito estava terrível."
        Você: "Imagino! Coisas do dia a dia, né? Mas me diga, há algo específico sobre as soluções da *{company_name}* que você gostaria de explorar hoje?"
        Outro Exemplo (Se o agente já tinha introduzido o tema da empresa):
        Você: "Entendo. Mudando um pouco de assunto, mas ainda sobre como a *{company_name}* pode te ajudar, você já teve chance de pensar sobre [aspecto geral relacionado à empresa/produto]?"

    *   **Dica:** O "Hint do Goal Interrompido" ({interrupted_goal_type_hint_text}) pode te dar uma pista sobre o tipo de conversa que estava acontecendo (ex: "INVESTIGATING_NEEDS", "PRESENTING_SOLUTION"). Use isso para guiar sua intuição sobre o melhor ponto de retorno.

4.  **Evitar Frases Clichês:** Tente NÃO usar frases muito batidas como "Voltando ao assunto anterior..." ou "Continuando de onde paramos..." a menos que seja a forma mais natural e concisa. Prefira referenciar o conteúdo.

5.  **Ser Conciso:** A resposta completa (reconhecimento + transição) deve ser curta e fluida.
6.  **Tom e Formatação:** Use o tom de vendas '{sales_tone}', idioma '{language}', e aplique a formatação WhatsApp ({formatting_instructions}).

**HISTÓRICO RECENTE DA CONVERSA (Analisar para transição):**
{chat_history}
--- Fim do Histórico ---

Gere APENAS a frase de reconhecimento e transição, de forma natural e eficaz.""",
        ),
    ]
)

PROMPT_PRESENT_SOLUTION_OFFER = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Você é um Assistente de Vendas IA persuasivo e claro, da '{company_name}'.
Sua tarefa é apresentar o produto/serviço '{product_name_to_present}', enfatizando como ele resolve o '{key_benefit_to_highlight}' para o cliente.
O produto e o benefício principal já foram selecionados para você.

**Produto Selecionado para Apresentação:** {product_name_to_present}
**Benefício Chave Principal a ser Destacado:** {key_benefit_to_highlight}

**Contexto Adicional (Use para enriquecer a descrição do produto, se relevante):**
- Informações do Perfil da Empresa:
  - Descrição do Negócio: {business_description}
  - Resumo das Ofertas (pode conter detalhes do '{product_name_to_present}'): {offering_summary}
  - Pontos Chave de Venda Gerais: {key_selling_points}
- Contexto Específico do Produto (RAG - se disponível e relevante para '{product_name_to_present}'):
  {rag_context}
--- Fim do Contexto Adicional ---

**Instruções para a Mensagem de Apresentação:**
1.  **Conexão Inicial:** Comece conectando a apresentação ao benefício chave ou à necessidade do cliente.
    Exemplo: "Considerando seu interesse em {key_benefit_to_highlight}, acredito que o *{product_name_to_present}* seja uma excelente opção para você."
    Ou: "Para resolver [problema/necessidade do cliente relacionado ao {key_benefit_to_highlight}], temos o *{product_name_to_present}*."
2.  **Descrição Focada:** Descreva brevemente o *{product_name_to_present}*. Explique COMO ele entrega o *{key_benefit_to_highlight}*.
    Use detalhes do "Contexto Adicional" (RAG ou Perfil da Empresa) para tornar a descrição mais concreta e valiosa, se esses detalhes forem específicos para o '{product_name_to_present}'.
3.  **Benefícios sobre Características:** Sempre traduza características em benefícios diretos para o cliente.
4.  **Chamada para Ação Suave:** Termine com uma pergunta aberta para verificar o interesse e convidar a uma próxima etapa.
    Exemplos: "Isso parece ser o que você procura?", "O que você acha desta solução para [contexto do benefício]?", "Gostaria de saber mais detalhes sobre como o *{product_name_to_present}* pode te ajudar com {key_benefit_to_highlight}?"
5.  **Tom e Formatação:** Use o tom de vendas '{sales_tone}', idioma '{language}', e aplique a formatação WhatsApp ({formatting_instructions}).

**Histórico Recente da Conversa (para seu contexto):**
{chat_history}
--- Fim do Histórico ---

Gere APENAS a mensagem de apresentação para o '{product_name_to_present}', focando no '{key_benefit_to_highlight}'.""",
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
            """Você é um Assistente de Vendas IA da '{company_name}', atencioso e proativo. O cliente não respondeu à sua última mensagem por um tempo.
Sua tarefa é enviar uma mensagem de follow-up gentil e contextualmente relevante para tentar reengajar o cliente, idealmente nos tópicos relacionados à '{company_name}'.

**Contexto da Conversa:**
- Sua última mensagem enviada ao cliente foi: "{last_agent_action_text_for_follow_up}"
- O objetivo principal que você (agente) estava perseguindo antes da pausa era relacionado a: '{goal_type_before_pause}'
- Esta é a tentativa de follow-up número: {current_follow_up_attempts_display} de {max_follow_up_attempts_total} no total.
- Idioma: {language}
- Tom de Vendas: {sales_tone} (use um tom ainda mais suave, compreensivo e menos insistente para follow-up)

**Instruções Cruciais para a Mensagem de Follow-up:**

1.  **Reconhecimento Suave da Pausa:**
    *   Comece de forma amigável (Varie, use o contexto e deixa o mais natural possível!)

2.  **Referência Contextual Inteligente com Foco no Retorno ao Tema da Empresa:**
    *   Consulte o "HISTÓRICO RECENTE".
    *   **Se a sua última mensagem ("{last_agent_action_text_for_follow_up}") foi uma resposta de fallback (ex: "não tenho essa informação") a uma pergunta específica do cliente sobre um tema não diretamente relacionado à '{company_name}':**
        *   **NÃO repita o fallback.**
        *   Reconheça brevemente o tópico do cliente, mas rapidamente tente conectar com os objetivos da '{company_name}' ou o '{goal_type_before_pause}'.
        *   Exemplo (Cliente perguntou sobre "mares serem pulmão do mundo", agente deu fallback, goal era "INVESTIGATING_NEEDS" sobre soluções da empresa):
            "Olá! Notei que nossa conversa deu uma pausa após sua pergunta interessante sobre os mares. Retomando o que conversávamos sobre [necessidade do cliente relacionada à empresa OU como a {company_name} pode ajudar], você gostaria de continuar ou precisa de mais um tempo para pensar sobre isso?"
            OU, se o tópico do cliente for muito distante:
            "Olá! Notei que nossa conversa deu uma pausa. Se ainda tiver interesse em explorar como a *{company_name}* pode te ajudar com [objetivo geral da empresa ou {goal_type_before_pause}], estou à disposição. Ou, se preferir, podemos conversar sobre [tópico do cliente] um pouco mais, e depois vemos como seguir." (Oferecer o tema do cliente como segunda opção).
    *   **Se a sua última mensagem foi uma pergunta ou afirmação sua que avançava um objetivo da '{company_name}' (relacionado a '{goal_type_before_pause}'):**
        *   Relembre sutilmente esse tópico ou o objetivo da empresa.
        *   Exemplo (Agente perguntou sobre necessidades, goal era INVESTIGATING_NEEDS):
            "Só para checar... estávamos conversando sobre como a *{company_name}* poderia ajudar com [aspecto da necessidade do cliente]. Você teve alguma nova reflexão sobre isso ou gostaria de explorar de outra forma?"
    *   **Se o contexto for muito inicial ou o ponto de retorno for vago:**
        *   Use uma abordagem mais geral para reengajar sobre os serviços/produtos da '{company_name}'.
        *   Exemplo: "Olá novamente! Só queria saber se há algo específico sobre as soluções da *{company_name}* em que posso te ajudar hoje, ou algum desafio que esteja enfrentando?"

3.  **Convite ao Reengajamento (Priorizando o Tema da Empresa):**
    *   **Primeiro Follow-up (tentativa 1 de {max_follow_up_attempts_total}):**
        "[Referência Contextual Inteligente com foco na empresa]. Gostaria de continuar nossa conversa sobre isso ou talvez precise de mais um momento para pensar? Estou à disposição!"
    *   **Follow-ups Intermediários (ex: tentativa 2 de 3):**
        "[Referência Contextual Inteligente com foco na empresa]. Há algo mais em que posso ajudar referente a isso ou alguma dúvida que surgiu sobre as soluções da *{company_name}*?"
    *   **Último Follow-up (tentativa {max_follow_up_attempts_total} de {max_follow_up_attempts_total}):**
        "[Referência Contextual Inteligente com foco na empresa]. Ainda estou por aqui se precisar de algo. Caso contrário, sem problemas, e agradeço seu tempo até aqui! Tenha um ótimo dia."

4.  **Naturalidade e Concisão:** Mantenha a mensagem curta, amigável e humana.
5.  **Formatação:** Aplique formatação WhatsApp sutil ({formatting_instructions}).

**HISTÓRICO RECENTE (para seu contexto de decisão, não para repetir ao usuário):**
{chat_history}
--- Fim do Histórico ---

Gere APENAS a mensagem de follow-up, buscando reengajar o cliente nos tópicos relevantes para a '{company_name}'.""",
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
        if action_command == "GENERATE_GREETING":
            combined_spin_type = action_params.get("combined_spin_question_type")
            specific_values["combined_spin_question_type_for_prompt"] = (
                combined_spin_type if combined_spin_type else "None"
            )  # Passar "None" como string
            if combined_spin_type:
                logger.info(
                    f"[{node_name}] GENERATE_GREETING will be combined with SPIN: {combined_spin_type}"
                )

        elif action_command == "ANSWER_DIRECT_QUESTION":
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
            combined_spin_type = action_params.get("combined_spin_question_type")
            specific_values["combined_spin_question_type_for_prompt"] = (
                (combined_spin_type) if combined_spin_type else "None"
            )

        elif action_command == "ASK_SPIN_QUESTION":
            specific_values["spin_type"] = action_params.get("spin_type", "Situation")
        elif action_command == "GENERATE_REBUTTAL":
            specific_values["objection_text"] = action_params.get(
                "objection_text_to_address", "[Objeção não especificada]"
            )
        elif action_command == "ASK_CLARIFYING_QUESTION":
            context_from_params = action_params.get("context")

            if (
                context_from_params
                and isinstance(context_from_params, str)
                and context_from_params.strip()
            ):
                vague_text_for_prompt = context_from_params
                last_action_context_for_prompt = context_from_params
            else:  # Fallback
                logger.warning(
                    f"[{node_name}] Context from action_params for ASK_CLARIFYING_QUESTION was empty or None. Falling back to goal_details."
                )
                vague_text_for_prompt = (
                    state.get("current_agent_goal", {})
                    .get("goal_details", {})
                    .get("text", "[Declaração vaga não especificada]")
                )
                last_action_context_for_prompt = (
                    "N/A"  # Or some other suitable fallback for this case
                )

            specific_values["vague_statement_text"] = vague_text_for_prompt
            specific_values["last_action_context"] = last_action_context_for_prompt

        elif action_command == "ACKNOWLEDGE_AND_TRANSITION":
            specific_values["off_topic_text"] = action_params.get(
                "off_topic_text", "[comentário não especificado]"
            )

            specific_values["interrupted_goal_type_hint_text"] = action_params.get(
                "interrupted_goal_type_hint",
                "o fluxo normal da conversa",
            )
        elif action_command == "PRESENT_SOLUTION_OFFER":
            selected_prompt = PROMPT_PRESENT_SOLUTION_OFFER
            specific_values["product_name_to_present"] = action_params.get(
                "product_name_to_present", "[Produto não especificado]"
            )
            specific_values["key_benefit_to_highlight"] = action_params.get(
                "key_benefit_to_highlight", "[Benefício não especificado]"
            )
            if (
                specific_values["product_name_to_present"]
                == "[Produto não especificado pelo planner]"
            ):
                logger.error(
                    f"[{node_name}] Critical: product_name_to_present not found in action_params for PRESENT_SOLUTION_OFFER."
                )

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
