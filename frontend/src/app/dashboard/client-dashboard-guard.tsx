// src/app/dashboard/ClientDashboardGuard.tsx
"use client";

import { useSubscription } from "@/contexts/subscription-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  AppBetaStatusEnum,
  AppBetaStatusEnumType,
  BetaTesterStatusResponse,
} from "@/lib/enums";
import { useUser } from "@clerk/nextjs";
import { AlertTriangle, Loader2 } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

// Rotas dentro do dashboard que são permitidas mesmo sem uma assinatura paga ativa
// ou para usuários que precisam gerenciar sua assinatura/beta.
const ALWAYS_ALLOWED_DASHBOARD_PATHS = ["/dashboard/account/subscription"];

export function ClientDashboardGuard({ children }: { children: ReactNode }) {
  const { isSignedIn, isLoaded: isClerkLoaded } = useUser();
  const {
    subscription, // Objeto SubscriptionRead | null
    isLoadingSubscription, // Booleano do useQuery da assinatura
    isErrorSubscription, // Booleano do useQuery da assinatura
    // hasActiveSubscription, // Derivado de 'subscription'
  } = useSubscription();

  const fetcher = useAuthenticatedFetch();
  const pathname = usePathname();
  const router = useRouter();

  // Estado para o status da solicitação beta
  const [betaCheckStatus, setBetaCheckStatus] = useState<
    | AppBetaStatusEnumType
    | "not_found"
    | "loading"
    | "error"
    | "not_checked"
    | "not_applicable"
  >("not_checked"); // not_checked: ainda não verificamos; not_applicable: não precisa verificar (tem sub paga)

  const [isInitialLogicComplete, setIsInitialLogicComplete] = useState(false);

  // Efeito para buscar status da assinatura e, se necessário, status beta
  useEffect(() => {
    if (!isClerkLoaded || !isSignedIn || !fetcher) {
      if (isClerkLoaded && !isSignedIn) setIsInitialLogicComplete(true); // Se não logado, marca como completo para evitar loader infinito
      return;
    }

    if (isLoadingSubscription) {
      console.log("ClientDashboardGuard: Aguardando dados da assinatura...");
      return; // Aguarda a query da assinatura resolver primeiro
    }

    // Se chegou aqui, isLoadingSubscription é false.
    // E isClerkLoaded, isSignedIn, fetcher são true.

    const performChecks = async () => {
      if (
        subscription &&
        (subscription.status === "active" || subscription.status === "trialing")
      ) {
        console.log(
          "ClientDashboardGuard: Assinatura ativa ou em trial encontrada. Verificação beta não aplicável."
        );
        setBetaCheckStatus("not_applicable");
        setIsInitialLogicComplete(true);
        return;
      }

      // Se tem assinatura mas com status problemático, a lógica de redirecionamento abaixo cuidará.
      // Não precisamos buscar status beta nesses casos, pois o problema da assinatura tem prioridade.
      if (
        subscription &&
        subscription.status !== "active" &&
        subscription.status !== "trialing"
      ) {
        console.log(
          "ClientDashboardGuard: Assinatura com status problemático. Verificação beta não aplicável neste momento."
        );
        setBetaCheckStatus("not_applicable"); // Ou um status específico de "sub_issue"
        setIsInitialLogicComplete(true);
        return;
      }

      // Se não há NENHUMA assinatura (subscription é null), então verificar status beta
      if (!subscription) {
        console.log(
          "ClientDashboardGuard: Nenhuma assinatura. Verificando status beta..."
        );
        setBetaCheckStatus("loading");
        try {
          const response = await fetcher("/api/v1/beta/my-status");
          if (response.ok) {
            const data: BetaTesterStatusResponse = await response.json();
            setBetaCheckStatus(data.status || "not_found");
          } else if (response.status === 404) {
            setBetaCheckStatus("not_found");
          } else {
            setBetaCheckStatus("error");
          }
        } catch (error) {
          setBetaCheckStatus("error");
        }
      }
      setIsInitialLogicComplete(true);
    };

    if (!isInitialLogicComplete) {
      // Só roda uma vez ou se as dependências mudarem
      performChecks();
    }
  }, [
    isClerkLoaded,
    isSignedIn,
    fetcher,
    isLoadingSubscription,
    subscription,
    isInitialLogicComplete,
  ]);

  // Efeito para redirecionamentos, SÓ DEPOIS que isInitialLogicComplete for true
  useEffect(() => {
    if (
      !isInitialLogicComplete ||
      isLoadingSubscription ||
      betaCheckStatus === "loading" ||
      betaCheckStatus === "not_checked"
    ) {
      return; // Aguarda todas as informações e a primeira checagem
    }

    const isAllowedPath = ALWAYS_ALLOWED_DASHBOARD_PATHS.some((path) =>
      pathname.startsWith(path)
    );
    if (isAllowedPath) {
      console.log(
        `ClientDashboardGuard (Redirect Logic): Rota ${pathname} é permitida. Sem redirecionamento.`
      );
      return;
    }

    // 1. Prioridade: Problemas com assinatura existente
    if (
      subscription &&
      subscription.status !== "active" &&
      subscription.status !== "trialing"
    ) {
      console.log(
        `ClientDashboardGuard (Redirect Logic): Assinatura com status '${subscription.status}'. Redirecionando para /dashboard/account/subscription.`
      );
      router.replace(
        "/dashboard/account/subscription?reason=subscription_issue"
      );
      return;
    }

    // 2. Se tem assinatura ativa/trialing, permite acesso (já que não é uma ALWAYS_ALLOWED_PATH)
    if (
      subscription &&
      (subscription.status === "active" || subscription.status === "trialing")
    ) {
      console.log(
        `ClientDashboardGuard (Redirect Logic): Assinatura '${subscription.status}'. Acesso permitido para ${pathname}.`
      );
      return;
    }

    // 3. Se não tem assinatura (subscription é null), usa o status beta para decidir
    if (!subscription) {
      switch (betaCheckStatus) {
        case AppBetaStatusEnum.APPROVED:
          console.log(
            `ClientDashboardGuard (Redirect Logic): Sem sub, Beta APROVADO. Redirecionando para /billing/plans.`
          );
          router.replace("/beta/status?reason=beta_approved");
          break;
        case AppBetaStatusEnum.PENDING_APPROVAL:
          console.log(
            `ClientDashboardGuard (Redirect Logic): Sem sub, Beta PENDENTE. Redirecionando para /beta/status.`
          );
          router.replace("/beta/status?reason=pending");
          break;
        case AppBetaStatusEnum.DENIED:
        case "not_found":
        case "error":
        default: // Inclui 'not_applicable' se chegou aqui sem sub, o que é estranho, mas trata como 'apply'
          console.log(
            `ClientDashboardGuard (Redirect Logic): Sem sub, status beta '${betaCheckStatus}'. Redirecionando para /beta/apply.`
          );
          router.replace("/beta/apply?reason=no_beta_access");
          break;
      }
    }
  }, [
    isInitialLogicComplete,
    isLoadingSubscription,
    subscription,
    betaCheckStatus,
    pathname,
    router,
  ]);

  // Feedback de carregamento inicial
  if (
    !isInitialLogicComplete ||
    isLoadingSubscription ||
    (betaCheckStatus === "loading" && !subscription)
  ) {
    return (
      <div className="flex h-screen w-full items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="ml-4 text-lg">Carregando seu ambiente...</p>
      </div>
    );
  }

  // Feedback de erro na busca da assinatura (se não for tratado por redirecionamento)
  if (
    isErrorSubscription &&
    !ALWAYS_ALLOWED_DASHBOARD_PATHS.some((path) => pathname.startsWith(path))
  ) {
    // Se betaCheckStatus levou a um redirecionamento, este return não será atingido.
    // Este é para o caso de erro na sub e o status beta não levar a um redirecionamento específico.
    return (
      <div className="flex h-screen w-full items-center justify-center p-4 text-center">
        <div>
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
          <h2 className="text-xl font-semibold text-red-700">
            Erro ao Carregar Dados da Conta
          </h2>
          <p className="text-muted-foreground">
            Não foi possível verificar sua assinatura. Tente novamente mais
            tarde.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
