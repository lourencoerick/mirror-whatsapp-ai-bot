from typing import Dict, List

MESSAGE_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "initial_contact": [
        {
            "template": "Oi, {customer_name}, tudo bem? Aqui é o {ai_name} da {company_name}. Pode me contar o que te trouxe aqui?",
            "intent": "introduction_with_known_name",
        },
        {
            "template": "Olá! Meu nome é {your_name}, sou especialista de produto aqui na {company_name}. Para começarmos, como posso te chamar?",
            "intent": "introduction_and_ask_name",
        },
        {
            "template": "Oi, tudo bem? Eu sou o {your_name}, da equipe {company_name}. Com quem eu tenho o prazer de falar hoje?",
            "intent": "introduction_and_ask_name",
        },
    ],
    "discovery": [
        {
            "template": "Oi {nome}, tudo bem? Aqui é {seu nome} da {nome da empresa} e vi que você acabou de acessar nosso site, foi isso mesmo?",
            "intent": "initial_contact_website",
        },
        {
            "template": "{nome}, você conseguiu entender certinho como funciona a nossa solução?",
            "intent": "check_understanding",
        },
        {
            "template": "Você já atua no {seu mercado}?",
            "intent": "check_market_experience",
        },
        {
            "template": "Você já conhece algo sobre {esse mercado}?",
            "intent": "check_market_knowledge",
        },
        {
            "template": "Atualmente você trabalha com o quê?",
            "intent": "check_profession",
        },
        {
            "template": "O que te levou hoje a buscar a {seu produto}?",
            "intent": "understand_motivation",
        },
        {
            "template": "Vi aqui que você não finalizou sua inscrição. Ficou com alguma dúvida ou teve alguma dificuldade?",
            "intent": "abandoned_cart_follow_up",
        },
        {
            "template": "Certo {nome}, antes de falarmos sobre {objeção}, você já conhece algo sobre {XPTO}?",
            "intent": "reframe_before_objection",
        },
        {
            "template": "Entendi {nome}, e esse {objetivo} é um plano para este ano ou para o próximo?",
            "intent": "understand_timeline",
        },
        {
            "template": "Atualmente, você está fazendo algo para {atingir o objetivo}?",
            "intent": "check_current_solutions",
        },
        {
            "template": "Aconteceu algo recentemente que te motivou a procurar {a solução que você oferta}?",
            "intent": "understand_trigger_event",
        },
        {
            "template": "Seu objetivo é mais pessoal ou profissional?",
            "intent": "check_goal_type",
        },
        {
            "template": "Caso a gente avance, essa decisão é somente sua ou você envolve mais alguém nesse projeto?",
            "intent": "check_decision_maker",
        },
        {
            "template": "O que você sabe sobre a {nome da empresa} ou nosso método {método XPTO}?",
            "intent": "check_brand_awareness",
        },
        {"template": "Como você conheceu a {empresa}?", "intent": "check_source"},
        {
            "template": "Existe algo que te impede hoje de se tornar nosso cliente?",
            "intent": "preemptive_objection_handling",
        },
        {
            "template": "Se você pudesse desenhar o {produto} perfeito, o que ele precisaria ter?",
            "intent": "understand_ideal_solution",
        },
        {
            "template": "Podemos conversar por aqui mesmo. Você tem uns 10 minutos de atenção agora?",
            "intent": "check_availability",
        },
        {
            "template": "Entendi o que você busca, {nome}. Como seu caso é bem específico, você teria um tempo para agendarmos um call com um especialista?",
            "intent": "propose_call",
        },
        {
            "template": "Entendo. Mas só para eu registrar aqui, você sentiu falta de algo na nossa solução?",
            "intent": "gather_feedback_on_rejection",
        },
        {
            "template": "Para eu ver se consigo te ajudar financeiramente, até qual valor você conseguiria investir?",
            "intent": "check_budget",
        },
        {
            "template": "Qual sua maior dificuldade hoje para {atingir o objetivo da solução}?",
            "intent": "understand_pain_point",
        },
        {
            "template": "Para atingir {objetivo proposto} é preciso uma dedicação de X horas por semana. Isso é possível para você hoje?",
            "intent": "check_commitment",
        },
        {
            "template": "Como foi sua experiência na última vez que tentou resolver essa dor?",
            "intent": "understand_past_attempts",
        },
        {
            "template": "Vi aqui que você baixou nosso e-book sobre {XPTO}. Chegou tudo certo no seu e-mail?",
            "intent": "follow_up_lead_magnet",
        },
    ],
    "qualification": [
        {
            "template": "Entendi seu objetivo, {nome}. E esse plano é para agora, para os próximos meses, ou mais para o longo prazo?",
            "intent": "qualify_timeline",
        },
        {
            "template": "Para eu entender a melhor forma de te ajudar, qual valor você estava pensando em investir para resolver isso?",
            "intent": "qualify_budget",
        },
        {
            "template": "Legal! E para essa decisão, é só você ou precisa conversar com mais alguém, como um sócio ou parceiro?",
            "intent": "qualify_authority",
        },
        {
            "template": "Para ter sucesso com {seu produto}, é ideal uma dedicação de X horas por semana. Isso se encaixa na sua rotina atual?",
            "intent": "qualify_commitment",
        },
        {
            "template": "Você já tem experiência no {seu mercado} ou está começando agora?",
            "intent": "qualify_experience_level",
        },
        {
            "template": "Qual é a sua maior prioridade no momento? É resolver {essa dor} ou há outras coisas mais urgentes?",
            "intent": "qualify_priority",
        },
        {
            "template": "Você já está usando alguma outra ferramenta ou método para tentar resolver isso?",
            "intent": "qualify_current_solution",
        },
        {
            "template": "O que te motivou a procurar uma solução para {seu nicho} exatamente agora?",
            "intent": "qualify_need_urgency",
        },
    ],
    "offering_presentation": [
        {
            "template": "Nossas aulas são ministradas por referências do mercado, garantindo que você aprenda com os melhores.",
            "intent": "present_feature_authority",
        },
        {
            "template": "Você tem acesso à plataforma 24 horas por dia, seja no computador ou no celular, para estudar no seu ritmo.",
            "intent": "highlight_benefit_flexibility",
        },
        {
            "template": "Nosso time de suporte está sempre disponível para tirar suas dúvidas, então você nunca fica travado no processo.",
            "intent": "highlight_benefit_support",
        },
        {
            "template": "E para sua total tranquilidade, oferecemos uma garantia incondicional de 7 dias. Se não for para você, devolvemos todo o seu investimento, sem perguntas.",
            "intent": "reverse_risk",
        },
        {
            "template": "Nosso objetivo é que você se torne um vendedor destaque, batendo suas metas e sendo reconhecido por isso.",
            "intent": "highlight_outcome",
        },
        {
            "template": "Já ajudamos mais de {X_mil} clientes a alcançarem seus objetivos, o que nos posiciona como líderes no mercado.",
            "intent": "provide_social_proof",
        },
        {
            "template": "Você também terá acesso à nossa comunidade exclusiva para fazer networking e trocar experiências, para nunca se sentir sozinho na jornada.",
            "intent": "highlight_benefit_community",
        },
        {
            "template": "Por termos toda essa expertise, aqui na {nome da empresa} seu objetivo de {resolver a dor} se torna um processo mais previsível e seguro.",
            "intent": "connect_feature_to_pain_point",
        },
        {
            "template": "De tudo que conversamos até aqui, {nome}, o que mais te chamou a atenção?",
            "intent": "check_engagement",
        },
        {
            "template": "Isso faz sentido para o que você está buscando?",
            "intent": "check_alignment",
        },
        {
            "template": "{nome}, sendo bem direto, o que falta para você tomar a decisão e começar a transformar seus resultados?",
            "intent": "trial_close",
        },
        {
            "template": "Se resolvermos a questão de {objeção}, podemos seguir em frente com a sua inscrição?",
            "intent": "isolate_objection",
        },
    ],
    "checkout_initiated": [
        {
            "template": "Então, {nome}, podemos ir para a parte do investimento? Ficou alguma dúvida sobre o que conversamos?",
            "intent": "confirm_and_transition_to_payment",
        },
        {
            "template": "O investimento para ter acesso a tudo isso é de apenas R$ {valor_do_produto}. Podemos seguir para o link de pagamento?",
            "intent": "state_price_and_ask_for_close",
        },
        {
            "template": "Perfeito! Para posso enviar o link de pagamento seguro? 📧",
            "intent": "request_payment_info",
        },
        {
            "template": "Ótimo! A inscrição será no seu nome mesmo, {nome}?",
            "intent": "assumptive_close_logistics",
        },
        {
            "template": "Então, {nome}, vamos garantir sua vaga agora? É só me confirmar que eu já gero seu link.",
            "intent": "direct_close_request",
        },
        {
            "template": "Então, para confirmar: {revisão_breve_dos_itens}. O valor total é R$ {valor_do_produto}. Tudo certo para fecharmos?",
            "intent": "summarize_and_close",
        },
    ],
    "objection_handling": [
        {
            "template": "{nome}, eu entendo perfeitamente sua preocupação com o investimento. Além do valor, existe mais algum ponto que te deixa em dúvida?",
            "intent": "handle_price_objection_isolate",
        },
        {
            "template": "Compreendo. Só para eu entender, comparado com o custo de continuar com {o problema atual}, como você enxerga esse investimento na solução?",
            "intent": "handle_price_objection_reframe_value",
        },
        {
            "template": "Faz sentido. Para que o valor se encaixe no seu orçamento, opções de parcelamento ajudariam?",
            "intent": "handle_price_objection_offer_solution",
        },
        {
            "template": "Tempo é realmente nosso bem mais precioso, eu concordo. A plataforma foi pensada justamente para te devolver tempo no futuro. Quanto você acha que economizaria por semana se {problema} estivesse resolvido?",
            "intent": "handle_time_objection_reframe_efficiency",
        },
        {
            "template": "Entendo a correria. O bom é que você pode começar com apenas {X horas} por semana e avançar no seu próprio ritmo. A flexibilidade é total.",
            "intent": "handle_time_objection_offer_flexibility",
        },
        {
            "template": "É totalmente normal ter essa dúvida. Por isso mesmo oferecemos a garantia de 7 dias. Você pode testar tudo sem risco algum e ver se realmente é para você.",
            "intent": "handle_trust_objection_leverage_guarantee",
        },
        {
            "template": "Vamos voltar ao que conversamos no início. Você me disse que seu maior desafio é {dor}. Se daqui a 6 meses esse problema estivesse resolvido, como isso impactaria seu dia a dia?",
            "intent": "handle_need_objection_revisit_pain",
        },
        {
            "template": "Claro, uma decisão importante como essa deve ser bem pensada. O que você acha que seu {sócio/esposa} acharia mais interessante em tudo que conversamos?",
            "intent": "handle_authority_objection_empower",
        },
    ],
    "follow_up_in_progress": [
        {
            "template": "Oi {nome}, só passando para saber se você teve um tempinho para pensar na nossa conversa. Se tiver qualquer dúvida, estou por aqui! 😊",
            "intent": "gentle_nudge",
        },
        {
            "template": "{nome}, tá por aí? Só queria checar se ficou alguma dúvida pendente que eu possa te ajudar a resolver.",
            "intent": "gentle_nudge",
        },
        {
            "template": "Olá {nome}, sei que a vida é corrida! Só para você saber, a condição especial que conversamos é válida até {data_limite}. Não queria que você perdesse a oportunidade. 😉",
            "intent": "value_add_urgency",
        },
        {
            "template": "Oi {nome}, só queria adicionar que, além do que conversamos, muitos clientes na sua situação também gostam de saber sobre {benefício_extra}. Talvez isso ajude na sua decisão!",
            "intent": "value_add_new_info",
        },
        {
            "template": "Olá {nome}, tentei contato algumas vezes, mas sem sucesso. Estou entendendo que talvez este não seja o melhor momento para você. Vou fechar nosso atendimento por aqui para não te incomodar, mas se mudar de ideia, as portas estarão sempre abertas. Tudo de bom!",
            "intent": "breakup_message",
        },
        {
            "template": "Entendido, {nome}. Agradeço muito seu tempo e sinceridade. Vou encerrar nosso contato por aqui, conforme você pediu. Se precisar de algo no futuro, é só chamar. Um abraço!",
            "intent": "confirm_closure_request",
        },
    ],
}
