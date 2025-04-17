"use client";

import React, { useEffect } from 'react';
import Link from 'next/link';
import { useLayoutContext } from '@/contexts/layout-context';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"; // Ajuste o caminho se necessário
import { Button } from "@/components/ui/button"; // Ajuste o caminho se necessário
import { Inbox, UserPlus, MessageSquareText, Bot } from 'lucide-react'; // Ícones para os passos

/**
 * Representa um único passo no guia de onboarding.
 */
interface OnboardingStepProps {
  icon: React.ElementType;
  title: string;
  description: string;
  link: string;
  linkLabel: string;
  disabled?: boolean; // Adicionado: flag opcional para desabilitar
}

/**
 * Renderiza um card representando um passo do onboarding.
 * @param {OnboardingStepProps} props - As propriedades para o passo de onboarding.
 * @returns {JSX.Element} O card do passo renderizado.
 */
const OnboardingStep: React.FC<OnboardingStepProps> = ({ icon: Icon, title, description, link, linkLabel, disabled = false }) => (
  <Card className="flex flex-col">
    <CardHeader className="flex-row items-center gap-4 pb-4">
      <span className="rounded-full bg-primary/10 p-2 text-primary">
        <Icon className="h-6 w-6" />
      </span>
      <CardTitle className="text-lg font-semibold">{title}</CardTitle>
    </CardHeader>
    <CardContent className="flex-grow">
      <p className="text-sm text-muted-foreground">{description}</p>
    </CardContent>
    <CardFooter>
      {/* Passa a prop 'disabled' para o componente Button */}
      {/* Remove a prop 'asChild' e o Link interno se estiver desabilitado */}
      <Button
        size="sm"
        className="w-full"
        disabled={disabled} // Aplica o estado desabilitado
        {...(!disabled && { asChild: true })} // Só usa asChild se NÃO estiver desabilitado
      >
        {disabled ? (
          linkLabel // Se desabilitado, apenas mostra o texto (ex: "Em breve")
        ) : (
          <Link href={link}>{linkLabel}</Link> // Se habilitado, renderiza o Link
        )}
      </Button>
    </CardFooter>
  </Card>
);


/**
 * A página principal do dashboard, incluindo um guia de onboarding para novos usuários.
 */
export default function DashboardPage() {
  const { setPageTitle } = useLayoutContext();

  useEffect(() => {
    setPageTitle("Home");
  }, [setPageTitle]);

  // Textos traduzidos para pt-BR e títulos revisados para concisão
  const onboardingSteps: OnboardingStepProps[] = [
    {
      icon: Inbox,
      title: "1. Caixa de Entrada", // Título revisado
      description: "Vincule seu canal do WhatsApp (Cloud API ou Evolution API) para começar a enviar e receber mensagens.",
      link: "/dashboard/inboxes",
      linkLabel: "Criar Caixa de Entrada", // Label revisado
    },
    {
      icon: UserPlus,
      title: "2. Adicionar Contatos",
      description: "Importe ou adicione manualmente os contatos com quem você deseja interagir pelo WhatsApp.",
      link: "/dashboard/contacts",
      linkLabel: "Gerenciar Contatos",
    },
    {
      icon: MessageSquareText,
      title: "3. Iniciar Conversa",
      description: "Comece sua primeira conversa manualmente ou prepare modelos para automação.",
      link: "/dashboard/conversations",
      linkLabel: "Ver Conversas",
    },
    {
      icon: Bot,
      title: "4. Configurar IA",
      description: "Configure seu vendedor IA para lidar com conversas automaticamente com base em seus objetivos.",
      link: "#", // Link pode ser '#' ou vazio, já que estará desabilitado
      linkLabel: "Em breve", // Texto alterado
      disabled: true, // Botão desabilitado
    },
  ];

  return (
    <div className="space-y-8 p-4 md:p-6 lg:p-8">
      {/* Seção de Onboarding */}
      <Card className="bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-slate-900 dark:via-slate-800 dark:to-purple-950">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Boas-vindas! Vamos começar</CardTitle>
          <CardDescription>
            Siga estes passos para configurar sua plataforma de automação de vendas pelo WhatsApp.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {onboardingSteps.map((step) => (
              <OnboardingStep key={step.title} {...step} />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Placeholder para outro conteúdo do dashboard */}
      {/* <div className="mt-8">
        <h2 className="text-xl font-semibold mb-4">Visão Geral do Dashboard</h2>
        <Card>
          <CardContent className="p-6">
            <p className="text-muted-foreground">
              (Outros widgets do dashboard como estatísticas, conversas recentes, etc. irão aqui...)
            </p>
          </CardContent>
        </Card>
      </div> */}
    </div>
  );
}