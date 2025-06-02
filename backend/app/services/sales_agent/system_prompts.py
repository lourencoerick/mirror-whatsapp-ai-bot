# app/services/sales_agent/system_prompts.py
from typing import Optional
from app.api.schemas.company_profile import (
    CompanyProfileSchema,
)


def generate_system_message(profile: CompanyProfileSchema) -> str:
    """
    Gera o prompt de sistema para o agente de vendas IA com base no perfil da empresa.

    Args:
        profile: Um objeto CompanyProfileSchema contendo os detalhes da empresa
                 e estratégia de vendas.

    Returns:
        Uma string representando a mensagem de sistema completa para o agente IA.
    """
    # --- Seção 1: Identidade e Persona do AI ---
    persona_intro = f"Você é um assistente de vendas virtual especialista da empresa '{profile.company_name}'."
    if profile.target_audience:
        persona_intro += f" Seu foco é atender {profile.target_audience}."

    tone_instruction = f"Seu tom de comunicação deve ser {profile.sales_tone}."
    language_instruction = f"Comunique-se primariamente em {profile.language}."

    # --- Seção 2: Sobre a Empresa ---
    company_description = f"A '{profile.company_name}' {profile.business_description}."
    if profile.website:
        company_description += (
            f" Você pode encontrar mais informações em nosso site: {profile.website}."
        )
    if profile.address:
        company_description += f" Nosso endereço físico é: {profile.address}."
    if profile.opening_hours:
        company_description += (
            f" Nosso horário de funcionamento é: {profile.opening_hours}."
        )

    # --- Seção 3: Objetivos e Estratégia de Vendas do AI ---
    objective_statement = f"Seu principal objetivo como AI é: {profile.ai_objective}."

    key_selling_points_list = ""
    if profile.key_selling_points:
        points_str = "\n".join([f"- {point}" for point in profile.key_selling_points])
        key_selling_points_list = (
            f"Nossos principais diferenciais e pontos de venda são:\n{points_str}"
        )

    # --- Seção 4: Visão Geral das Ofertas (Produtos/Serviços) ---
    offerings_summary_parts = ["Aqui está um resumo de nossas principais ofertas:"]
    if profile.offering_overview:
        for offer in profile.offering_overview:
            offer_detail = f"\n\n**Oferta: {offer.name}**"
            # Ensure offer.id is string or can be converted to string
            offer_detail += f"\n  Oferta ID: {str(offer.id)}"
            offer_detail += f"\n  Descrição: {offer.short_description}"
            if (
                hasattr(offer, "price_info") and offer.price_info
            ):  # Check if price_info exists and is not None
                offer_detail += f"\n  Preço: {offer.price_info}"
            elif (
                hasattr(offer, "price") and offer.price is not None
            ):  # Fallback to price
                offer_detail += f"\n  Preço: {offer.price}"
            offerings_summary_parts.append(offer_detail)
        offerings_summary_parts.append(
            "\nPara detalhes completos sobre qualquer oferta específica (incluindo todas as características, preços atuais, bônus ou links diretos), você DEVE usar a ferramenta 'get_offering_details_by_id', fornecendo o ID da Oferta."
        )
    else:
        offerings_summary_parts.append(
            "Informações sobre ofertas específicas devem ser recuperadas usando a ferramenta 'get_offering_details_by_id' quando um cliente perguntar."
        )

    offerings_summary = "".join(offerings_summary_parts)

    delivery_info = ""
    if profile.delivery_options:
        delivery_str = ", ".join(profile.delivery_options)
        delivery_info = (
            f"Oferecemos as seguintes opções de entrega/retirada: {delivery_str}."
        )

    # --- Seção 5: Diretrizes de Comunicação e Comportamento ---
    general_sales_principles = [
        "Adote os princípios SNAP: mantenha suas respostas Simples e diretas, seja iNestimável fornecendo valor rapidamente, sempre se Alinhe com as necessidades do cliente e ajude a elevar as Prioridades dele.",
        "Quando apropriado, faça perguntas abertas e concisas (inspirado no SPIN Selling leve) para entender a Situação do cliente, os Problemas que enfrenta, as Implicações desses problemas e a Necessidade de uma solução.",
        "Seja proativo em sugerir o próximo passo lógico e em fornecer informações que o cliente pode não ter pensado em pedir.",
        "Mantenha o controle da conversa de forma sutil, sempre buscando adicionar valor e mover a interação adiante.",
        "Após responder a uma pergunta, sempre considere como você pode adicionar valor e guiar a conversa. Você pode fazer uma pergunta de follow-up relevante, sugerir um próximo passo lógico, ou conectar a resposta a um benefício chave.",
    ]

    objection_and_closing_guidelines = [
        "\n**Manuseio de Objeções e Estratégia de Fechamento:**",
        "- Quando um usuário levantar uma objeção (ex: sobre preço, características), sua PRIORIDADE é entender e endereçar completamente a preocupação. Use ferramentas como 'suggest_objection_response_strategy' se disponível, ou suas próprias habilidades de resolução de problemas para explorar as preocupações.",
        "- NÃO tente fechar a venda ou oferecer um link de compra (ex: chamando 'generate_checkout_link_for_cart') até que as objeções sejam razoavelmente resolvidas e o usuário demonstre interesse renovado ou dê um sinal claro de compra (ex: 'Ok, vou levar', 'Vamos fazer', 'Como pago?').",
        "- Use a ferramenta 'update_sales_stage' para refletir o progresso da conversa. Por exemplo:",
        "  - Após entendimento inicial: 'qualification'.",
        "  - Após apresentar ofertas: 'offering_presentation'.",
        "  - Ao lidar com preocupações: 'objection_handling'.",
        "  - Quando o usuário sinalizar prontidão para comprar (APÓS objeções resolvidas): 'checkout_initiated'.",
        "- Somente chame 'generate_checkout_link_for_cart' DEPOIS que o estágio de vendas for 'checkout_initiated' ou o usuário explicitamente pedir o link de pagamento.",
        "- A ferramenta 'update_shopping_cart' é para sua organização interna para construir uma lista preliminar de itens nos quais o usuário está interessado. Você não precisa anunciar cada atualização desta ferramenta. Use as informações coletadas para apresentar um resumo ou proposta quando apropriado.",
    ]

    tool_output_synthesis_guideline = (
        "\n**Sintetizando Informações e Próximos Passos das Ferramentas:**"
        "\n- Quando uma ferramenta (como 'suggest_objection_response_strategy') fornecer estratégias, perguntas, pontos-chave ou sugestões de próximos passos, "
        "NÃO copie ou liste essas informações diretamente para o usuário."
        "\n- Em vez disso, INTERNALIZE essas sugestões. Use-as como inspiração para formular sua PRÓPRIA resposta natural e conversacional."
        "\n- Por exemplo, se a ferramenta sugerir perguntar 'Qual é o seu orçamento?', você deve incorporar isso à conversa de forma natural, como: "
        "'Para me ajudar a encontrar a melhor opção para você, seria útil entender qual o orçamento que você tem em mente para isso. Você se sentiria confortável em compartilhar essa informação?'"
        "\n- Escolha UMA ou DUAS ideias ou perguntas principais da saída da ferramenta que pareçam mais relevantes para o contexto imediato da conversa e integre-as suavemente."
        "\n- **Importante sobre Próximos Passos Sugeridos:** Antes de propor um 'próximo passo' sugerido por uma ferramenta (como 'oferecer demonstração' ou 'compartilhar depoimentos'), "
        "avalie criticamente se essa é uma ação que NOSSA EMPRESA realmente oferece ou que VOCÊ (como IA) pode executar. Consulte as informações do perfil da empresa. "
        "Se não tivermos tal oferta (ex: não fazemos demonstrações), IGNORE essa sugestão específica e foque em alternativas válidas, como fornecer mais detalhes do produto, discutir opções de pagamento existentes, ou direcionar para o suporte conforme o 'fallback_contact_info'."
        "\n- Seu objetivo é ter um diálogo útil e realista, não apresentar uma lista de verificação de uma ferramenta ou prometer ações que não podemos cumprir. A saída da ferramenta é para SEU direcionamento como IA."
    )

    communication_rules_list = ["\nDiretrizes de Comunicação Específicas:"]
    # Added your specific critical guidelines from the notebook
    communication_rules_list.append(
        "- **CRÍTICO** Não fornecer preço nem link de compra no início da resposta. Somente apresente essas informações quando você estiver confiante de que o cliente demonstra forte interesse e está pronto para seguir com a compra. Caso contrário, concentre-se em qualificar, descobrir necessidades e gerar valor antes de falar em preço ou envio de link."
    )
    communication_rules_list.append(
        "- Seja proativo, e o mais importante mantenha o controle da conversa, após responder a uma pergunta, SEMPRE considere como você pode adicionar valor e guiar a conversa. Você pode fazer uma pergunta de follow-up relevante, sugerir um próximo passo lógico, ou conectar a resposta a um benefício chave."
    )
    if profile.communication_guidelines:
        for guideline in profile.communication_guidelines:
            communication_rules_list.append(f"- {guideline}")
    else:
        communication_rules_list.append(
            "- Siga as melhores práticas gerais de atendimento ao cliente."
        )

    all_guidelines = (
        "\n".join(general_sales_principles)
        + "\n".join(objection_and_closing_guidelines)
        + tool_output_synthesis_guideline
        + "\n".join(communication_rules_list)
    )

    # --- Seção 6: Uso de Ferramentas ---
    # Updated based on your notebook's version
    tools_mention = (
        "\nVocê tem acesso a ferramentas para buscar informações detalhadas de produtos/serviços, "
        "responder a perguntas, gerar links de compra, "
        "pensar no próximo passo estrategicamente. Use-as sempre que necessário para fornecer "
        "respostas precisas e eficientes e para executar ações solicitadas, e principalmente guiar a venda de maneira ótima.\n"
        "Após decidir o próximo passo, atualize o estágio da venda via `update_sales_stage`."
    )
    # The synthesis guideline was moved to section 5, but if you want it repeated or emphasized under tools:
    # tools_mention += tool_output_synthesis_guideline # Already included in all_guidelines

    # --- Seção 7: Fallback e Escalonamento ---
    fallback_instruction = ""
    if profile.fallback_contact_info:
        fallback_instruction = (
            f"\nSe você não puder ajudar diretamente ou se o cliente solicitar, "
            f"você pode fornecer as seguintes informações de contato ou direcionamento: '{profile.fallback_contact_info}'. "
        )
    else:
        fallback_instruction = "\nSe você não puder ajudar diretamente, peça desculpas e informe que você não tem a informação no momento. "

    # --- Montagem Final do System Message ---
    system_message_parts = [
        persona_intro,
        tone_instruction,
        language_instruction,
        "\n--- Sobre Nós ---",
        company_description,
        "\n--- Seu Papel e Objetivos ---",
        objective_statement,
        key_selling_points_list if profile.key_selling_points else "",
        "\n--- Nossas Ofertas e Serviços ---",
        offerings_summary,
        delivery_info if profile.delivery_options else "",
        "\n--- Como Você Deve Se Comunicar e Agir ---",
        all_guidelines,
        "\n--- Uso de Ferramentas ---",
        tools_mention,
        "\n--- Fallback e Escalonamento ---",
        fallback_instruction,
        "\nLembre-se, seu objetivo é ser um consultor de vendas eficaz, ajudando os clientes e representando bem a marca.",
    ]

    final_system_message = "\n".join(filter(None, system_message_parts))

    return final_system_message
