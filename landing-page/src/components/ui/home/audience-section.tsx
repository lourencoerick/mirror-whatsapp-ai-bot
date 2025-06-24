// components/landing/AudienceSection.tsx
"use client";

import {
    CalendarCheck,
    Gem,
    Rocket,
    Store,
} from "lucide-react";
import { useRouter } from "next/navigation";
import React from "react";
import { Link as ScrollLink } from "react-scroll";


const AudienceSection = (): React.ReactElement => {
  const router = useRouter();
  
  const handleClick = (href: string): void => {
      router.push(`/#${href}`);
  };    
  const audiences = [
    {
      icon: <Rocket size={40} className="text-primary" />,
      title: "Infoprodutores & Experts Digitais",
      description:
        "Automatize o atendimento em lançamentos, recupere boletos e vendas no cartão com uma IA que vende seu produto 24/7.",
    },
    {
      icon: <CalendarCheck size={40} className="text-primary" />,
      title: "Clínicas e Profissionais da Saúde/Direito",
      description:
        "Deixe a IA qualificar pacientes/clientes e agendar consultas direto no seu Google Calendar. Foque apenas no atendimento de alto nível.",
    },
    {
    icon: <Gem size={40} className="text-primary" />, // Ícone que remete a algo valioso
    title: "Vendas Consultivas / Alto Ticket",
    description:
        "Otimize seu funil de vendas. Deixe a IA qualificar os leads, para que você dedique seu tempo apenas às negociações e propostas de alto valor.",
    },
    {
      icon: <Store size={40} className="text-primary" />,
      title: "Serviços & Negócios Locais",
      description:
        "Sua recepcionista virtual. Agenda horários para seu salão e responde clientes fora do expediente.",
    },
  ];


  return (
    <div className="mb-12 md:mb-20 bg-background text-foreground">
      <div className="container mx-auto px-6">
        <div className="text-center max-w-3xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-normal mb-4">
            Feito para quem transforma conversas em resultados
          </h2>
          <p className="text-lg mb-12">
            Se o seu negócio depende de <span className="font-bold">agendamentos e vendas pelo WhatsApp</span>,
            nossa IA não é uma ferramenta. <span className="font-bold">É o seu melhor funcionário.</span>
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-8 max-w-4xl mx-auto"> {/* Alterado para 2 colunas para dar mais destaque */}
          {audiences.map((audience, index) => (
            <div
              key={index}
              className="bg-card p-6 rounded-lg shadow-md text-left flex items-start space-x-4 border"
            >
              <div className="flex-shrink-0 mt-1">{audience.icon}</div>
              <div>
                <h3 className="font-bold text-xl mb-2">{audience.title}</h3>
                <p className="text-card-foreground/80">
                  {audience.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="text-center mt-12">
          <p className="text-lg">
            Seu cenário não está aqui? Se você usa WhatsApp para vender,{" "}
            <ScrollLink
                href="#pricing"
                activeClass="active"
                to="pricing"
                spy={true}
                smooth={true}
                offset={-50}
                duration={500}
                className="cursor-pointer"
                onClick={() => handleClick("pricing")}
                aria-label="Escolha um de nossos planos"
            >
                <span className="text-primary font-bold underline">nós podemos te ajudar.</span>
                
            </ScrollLink>
          </p>
        </div>
      </div>
    </div>
  );
};

export default AudienceSection;