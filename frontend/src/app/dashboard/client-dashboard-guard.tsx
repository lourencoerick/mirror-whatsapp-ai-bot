"use client";

import { useSubscription } from "@/contexts/subscription-context";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

const PUBLIC_DASHBOARD_PATHS_OR_MANAGEMENT = [
  "/dashboard/account/subscription", // Para gerenciar ou ver que não tem
];

export function ClientDashboardGuard({ children }: { children: ReactNode }) {
  const {
    hasActiveSubscription,
    planTier,
    isLoadingSubscription,
    isErrorSubscription,
    subscription,
  } = useSubscription();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (isLoadingSubscription) {
      console.log("ClientDashboardGuard: Aguardando dados da assinatura...");
      return;
    }

    if (isErrorSubscription) {
      console.error(
        "ClientDashboardGuard: Erro ao buscar dados da assinatura. Acesso pode ser restrito."
      );
      return;
    }

    const isAllowedPathWithoutActiveSub =
      PUBLIC_DASHBOARD_PATHS_OR_MANAGEMENT.some((path) =>
        pathname.startsWith(path)
      );

    // Cenário 1: Usuário não tem assinatura ativa e está tentando acessar uma rota protegida
    if (!hasActiveSubscription && !isAllowedPathWithoutActiveSub) {
      console.log(
        `ClientDashboardGuard: Usuário sem assinatura ativa em rota protegida (${pathname}). Redirecionando para planos.`
      );
      router.replace("/billing/plans?reason=subscription_required");
      return;
    }

    // Cenário 2: Status problemático da assinatura (ex: past_due, unpaid)
    // Redireciona para a página de gerenciamento de assinatura se não estiver já lá ou na página de planos.
    const problematicStatus =
      subscription &&
      (subscription.status === "past_due" ||
        subscription.status === "unpaid" ||
        // Se cancelada imediatamente (não apenas agendada para o fim do período)
        (subscription.status === "canceled" &&
          !subscription.cancel_at_period_end &&
          subscription.ended_at &&
          new Date(subscription.ended_at) <= new Date()));

    if (problematicStatus && !isAllowedPathWithoutActiveSub) {
      console.log(
        `ClientDashboardGuard: Status problemático da assinatura (${subscription?.status}) em ${pathname}. Redirecionando para gerenciamento.`
      );
      router.replace(
        "/dashboard/account/subscription?reason=manage_subscription"
      );
      return;
    }

    // Você pode adicionar mais lógicas aqui, como verificação de tier específico para certas rotas
    // Exemplo:
    // const requiresProTier = pathname.startsWith('/dashboard/pro-feature');
    // if (requiresProTier && planTier !== 'pro' && !isAllowedPathWithoutActiveSub) {
    //   console.log(`ClientDashboardGuard: Rota ${pathname} requer plano Pro. Usuário tem ${planTier}. Redirecionando.`);
    //   router.replace('/dashboard/billing/plans?reason=upgrade_required&feature=pro');
    //   return;
    // }
  }, [
    hasActiveSubscription,
    planTier,
    isLoadingSubscription,
    isErrorSubscription,
    pathname,
    router,
    subscription,
  ]);

  // Feedback visual enquanto a lógica de assinatura está sendo processada e pode redirecionar
  if (isLoadingSubscription) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="ml-4 text-lg">Verificando sua assinatura...</p>
      </div>
    );
  }

  // Se um redirecionamento for necessário, o useEffect o fará.
  // Enquanto isso, ou se nenhum redirecionamento for necessário, renderiza os filhos.
  // Poderíamos adicionar uma verificação aqui para não renderizar children se um redirecionamento estiver iminente,
  // mas o piscar de conteúdo pode ser mínimo.
  const isAllowedPathWithoutActiveSub =
    PUBLIC_DASHBOARD_PATHS_OR_MANAGEMENT.some((path) =>
      pathname.startsWith(path)
    );
  if (
    !isLoadingSubscription &&
    !isErrorSubscription &&
    !hasActiveSubscription &&
    !isAllowedPathWithoutActiveSub
  ) {
    // Se ainda não redirecionou e não deveria estar aqui, mostra carregando para o redirecionamento
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="ml-4 text-lg">Redirecionando...</p>
      </div>
    );
  }

  return <>{children}</>;
}
