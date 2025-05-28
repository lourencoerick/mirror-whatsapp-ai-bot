// src/contexts/subscription-context.tsx
"use client";

import { getPlanDetailsByStripeIds } from "@/config/billing-plans";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { getMySubscription } from "@/lib/api/billing";
import { components } from "@/types/api";
import { useAuth, useUser } from "@clerk/nextjs";
import {
  QueryObserverResult,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { createContext, ReactNode, useContext } from "react";

type SubscriptionData =
  | components["schemas"]["SubscriptionRead"]
  | null
  | undefined;

interface SubscriptionContextType {
  subscription: SubscriptionData;
  isLoadingSubscription: boolean;
  isErrorSubscription: boolean;
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
  const { isSignedIn, isLoaded: isClerkLoaded } = useAuth();
  const { user } = useUser();
  const fetcher = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  const queryEnabled = isClerkLoaded && isSignedIn && !!fetcher;

  const {
    data: subscription,
    isLoading: isLoadingQuery,
    isError,
    error,
    refetch,
  } = useQuery<SubscriptionData, Error>({
    queryKey: ["mySubscription", user?.id],
    queryFn: async () => {
      console.log(
        "[SubscriptionProvider] queryFn: Executando getMySubscription..."
      );

      return getMySubscription(fetcher!);
    },
    enabled: queryEnabled,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: true,
  });

  const isLoadingContext = !isClerkLoaded || (isSignedIn && isLoadingQuery);

  const hasActivePaidSubscription = !!(
    subscription &&
    (subscription.status === "active" || subscription.status === "trialing")
  );

  let effectivePlanTier: string | null = null;
  if (isLoadingContext) {
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

  return (
    <SubscriptionContext.Provider
      value={{
        subscription,
        isLoadingSubscription: isLoadingContext,
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
