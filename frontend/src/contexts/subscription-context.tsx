// src/contexts/subscription-context.tsx
"use client";

import { getPlanDetailsByStripeIds } from "@/config/billing-plans";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { getMySubscription } from "@/lib/api/billing";
import { components } from "@/types/api";
import { useAuth, useUser } from "@clerk/nextjs"; // Importe useUser também
import {
  QueryObserverResult,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { createContext, ReactNode, useContext } from "react";

type SubscriptionData = components["schemas"]["SubscriptionRead"] | null;

interface SubscriptionContextType {
  subscription: SubscriptionData;
  isLoadingSubscription: boolean; // Renomeado para clareza
  isErrorSubscription: boolean; // Renomeado para clareza
  subscriptionError: Error | null;
  hasActiveSubscription: boolean;
  planTier: string | null;
  refetchSubscription: () => Promise<
    QueryObserverResult<SubscriptionData, Error>
  >;
  invalidateSubscriptionQuery: () => void;
}

const SubscriptionContext = createContext<SubscriptionContextType | undefined>(
  undefined
);

export function SubscriptionProvider({ children }: { children: ReactNode }) {
  const { isSignedIn, isLoaded: isClerkLoaded } = useAuth(); // isLoaded indica se o Clerk terminou de carregar
  const { user } = useUser(); // Para forçar re-render quando o usuário mudar
  const fetcher = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  // A query só deve ser habilitada DEPOIS que o Clerk carregou E o usuário está logado E o fetcher está pronto.
  const queryEnabled = isClerkLoaded && isSignedIn && !!fetcher;

  const {
    data: subscription,
    isLoading: isLoadingQuery, // Este é o isLoading do useQuery em si
    isError,
    error,
    refetch,
  } = useQuery<SubscriptionData, Error>({
    queryKey: ["mySubscription", user?.id], // Adicionar user.id à chave para refetch automático no login/logout
    queryFn: async () => {
      console.log(
        "[SubscriptionProvider] queryFn: Executando getMySubscription..."
      );
      // A condição queryEnabled já garante isSignedIn e fetcher
      return getMySubscription(fetcher!); // Usar '!' pois queryEnabled garante que fetcher existe
    },
    enabled: queryEnabled, // Usar a flag combinada
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: true, // Mantenha true ou conforme sua preferência global
  });

  // Estado de carregamento geral para o contexto:
  // Considera o carregamento do Clerk E o carregamento da query (se habilitada)
  const isLoadingContext = !isClerkLoaded || (isSignedIn && isLoadingQuery);

  const hasActivePaidSubscription = !!(
    subscription &&
    (subscription.status === "active" || subscription.status === "trialing")
  );

  let effectivePlanTier: string | null = null;
  if (isLoadingContext) {
    // Usa o isLoadingContext
    effectivePlanTier = "loading";
  } else if (!isSignedIn) {
    effectivePlanTier = null;
  } else if (hasActivePaidSubscription && subscription?.stripe_product_id) {
    effectivePlanTier =
      getPlanDetailsByStripeIds(subscription.stripe_product_id)?.tier ||
      `unknown_paid_plan (${subscription.stripe_product_id.slice(-4)})`;
  } else {
    effectivePlanTier = isError ? "error_fetching" : "free";
  }

  const invalidateSubscriptionQuery = () => {
    queryClient.invalidateQueries({ queryKey: ["mySubscription", user?.id] });
  };

  // Log para depuração
  // console.log(`[SubscriptionProvider] isClerkLoaded: ${isClerkLoaded}, isSignedIn: ${isSignedIn}, fetcher: ${!!fetcher}, queryEnabled: ${queryEnabled}, isLoadingQuery: ${isLoadingQuery}, isLoadingContext: ${isLoadingContext}, subscription:`, subscription);

  return (
    <SubscriptionContext.Provider
      value={{
        subscription,
        isLoadingSubscription: isLoadingContext, // Expor o estado de carregamento combinado
        isErrorSubscription: isError,
        subscriptionError: error,
        hasActiveSubscription: hasActivePaidSubscription,
        planTier: effectivePlanTier,
        refetchSubscription: refetch,
        invalidateSubscriptionQuery,
      }}
    >
      {children}
    </SubscriptionContext.Provider>
  );
}

export function useSubscription() {
  const context = useContext(SubscriptionContext);
  if (context === undefined) {
    throw new Error(
      "useSubscription must be used within a SubscriptionProvider"
    );
  }
  return context;
}
