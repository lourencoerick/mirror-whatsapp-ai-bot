// app/dashboard/account/subscription/page.tsx
"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PLAN_DETAILS_MAP } from "@/config/billing-plans";
import { useLayoutContext } from "@/contexts/layout-context";
import { useSubscription } from "@/contexts/subscription-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { createCustomerPortalSession } from "@/lib/api/billing";
import { components } from "@/types/api";
import { useMutation } from "@tanstack/react-query";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  AlertCircle,
  AlertTriangle,
  CalendarDays,
  CheckCircle,
  Edit,
  ExternalLink,
  Loader2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

type CustomerPortalSessionResponse =
  components["schemas"]["CustomerPortalSessionResponse"];

export default function AccountSubscriptionPage() {
  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle?.("Minha Assinatura");
  }, [setPageTitle]);

  const fetcher = useAuthenticatedFetch();
  const [portalError, setPortalError] = useState<string | null>(null);

  const {
    subscription,
    isLoadingSubscription,
    isErrorSubscription,
    subscriptionError,
    // refetchSubscription, // Disponível se precisar de um refetch manual
  } = useSubscription();

  // Log para depuração do estado do contexto
  useEffect(() => {
    console.log("AccountSubscriptionPage - Context State Update:");
    console.log("  isLoading:", isLoadingSubscription);
    console.log("  isError:", isErrorSubscription);
    console.log("  subscription:", subscription);
    console.log("  subscriptionError:", subscriptionError);
  }, [
    subscription,
    isLoadingSubscription,
    isErrorSubscription,
    subscriptionError,
  ]);

  const mutation = useMutation<CustomerPortalSessionResponse, Error, void>({
    mutationFn: () => {
      if (!fetcher) {
        throw new Error("Autenticação necessária para acessar o portal.");
      }
      return createCustomerPortalSession(fetcher);
    },
    onSuccess: (data) => {
      if (data.portal_url) {
        window.location.href = data.portal_url;
      } else {
        console.error("Portal URL não recebida:", data);
        setPortalError(
          "Não foi possível obter o link para o portal de gerenciamento."
        );
      }
    },
    onError: (error) => {
      console.error("Erro ao criar sessão do portal:", error);
      setPortalError(
        error.message || "Falha ao acessar o portal de gerenciamento."
      );
    },
  });

  const handleManageSubscription = () => {
    setPortalError(null);
    mutation.mutate();
  };

  const getPlanDisplayName = (
    priceId?: string,
    productId?: string | null
  ): string => {
    // Tenta primeiro por Product ID, pois geralmente é mais genérico para o "plano"
    if (productId && PLAN_DETAILS_MAP[productId]) {
      return PLAN_DETAILS_MAP[productId].name;
    }
    // Depois tenta por Price ID
    if (priceId && PLAN_DETAILS_MAP[priceId]) {
      return PLAN_DETAILS_MAP[priceId].name;
    }

    // Fallbacks se não houver mapeamento, para ajudar na depuração
    if (productId) return `Plano (ID Produto: ${productId.slice(0, 12)}...)`; // Mostra parte do ID
    if (priceId) return `Plano (ID Preço: ${priceId.slice(0, 12)}...)`;

    return "Plano não identificado";
  };

  const renderSubscriptionDetails = () => {
    // Se está carregando e ainda não tem dados de assinatura (primeira carga)
    if (isLoadingSubscription && !subscription) {
      // Este estado é coberto pelo loader principal abaixo, mas pode ser útil
      // se você quiser um loader específico dentro do Card.
      // Por agora, o loader principal é suficiente.
    }

    if (!subscription) {
      return (
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>Nenhuma Assinatura Ativa</CardTitle>
            <CardDescription>
              Você ainda não possui uma assinatura ativa em nossa plataforma.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/dashboard/billing/plans">
              {" "}
              <Button>Ver Planos Disponíveis</Button>
            </Link>
          </CardContent>
        </Card>
      );
    }

    let statusColor = "text-gray-500";
    let StatusIconComponent = CalendarDays;
    let statusText =
      subscription.status.charAt(0).toUpperCase() +
      subscription.status.slice(1);

    switch (subscription.status) {
      case "active":
        statusColor = "text-green-600";
        StatusIconComponent = CheckCircle;
        statusText = "Ativa";
        break;
      case "trialing":
        statusColor = "text-blue-600";
        StatusIconComponent = CheckCircle;
        statusText = "Em Teste";
        break;
      case "past_due":
        statusColor = "text-orange-600";
        StatusIconComponent = AlertTriangle;
        statusText = "Pagamento Pendente";
        break;
      case "canceled":
        statusColor = "text-red-600";
        StatusIconComponent = XCircle;
        statusText = "Cancelada";
        break;
      case "unpaid":
        statusColor = "text-red-600";
        StatusIconComponent = AlertCircle;
        statusText = "Não Paga";
        break;
      default:
        statusText = `Status: ${subscription.status}`;
    }

    return (
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle className="text-2xl">Detalhes da sua Assinatura</CardTitle>
          <CardDescription>
            Gerencie sua assinatura e informações de pagamento através do nosso
            portal seguro do Stripe.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          {" "}
          {/* Aumentado space-y e pt */}
          <div className="flex justify-between items-center border-b pb-3">
            <span className="text-sm text-muted-foreground">Plano Atual:</span>
            <span className="font-semibold text-lg">
              {getPlanDisplayName(
                subscription.stripe_price_id,
                subscription.stripe_product_id
              )}
            </span>
          </div>
          <div className="flex justify-between items-center border-b pb-3">
            <span className="text-sm text-muted-foreground">Status:</span>
            <span
              className={`font-semibold ${statusColor} flex items-center text-lg`}
            >
              <StatusIconComponent className="w-5 h-5 mr-2 flex-shrink-0" />
              {statusText}
            </span>
          </div>
          {subscription.current_period_start && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">
                Início do Período Atual:
              </span>
              <span>
                {format(
                  new Date(subscription.current_period_start),
                  "dd 'de' MMMM 'de' yyyy",
                  { locale: ptBR }
                )}
              </span>
            </div>
          )}
          {subscription.current_period_end && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">
                {subscription.cancel_at_period_end &&
                subscription.status !== "canceled"
                  ? "Acesso válido até:"
                  : "Próxima Cobrança / Renovação:"}
              </span>
              <span>
                {format(
                  new Date(subscription.current_period_end),
                  "dd 'de' MMMM 'de' yyyy",
                  { locale: ptBR }
                )}
              </span>
            </div>
          )}
          {subscription.status === "trialing" && subscription.trial_ends_at && (
            <Alert
              variant="default"
              className="bg-blue-50 border-blue-300 text-blue-700"
            >
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <div className="ml-3">
                <AlertTitle className="font-semibold">
                  Período de Teste Ativo
                </AlertTitle>
                <AlertDescription>
                  Seu acesso gratuito termina em{" "}
                  {format(
                    new Date(subscription.trial_ends_at),
                    "dd/MM/yyyy 'às' HH:mm",
                    { locale: ptBR }
                  )}
                  .
                </AlertDescription>
              </div>
            </Alert>
          )}
          {subscription.cancel_at_period_end &&
            subscription.status !== "canceled" && (
              <Alert
                variant="default"
                className="bg-yellow-50 border-yellow-300 text-yellow-700"
              >
                <AlertTriangle className="h-5 w-5 flex-shrink-0" />
                <div className="ml-3">
                  <AlertTitle className="font-semibold">
                    Cancelamento Agendado
                  </AlertTitle>
                  <AlertDescription>
                    Sua assinatura será cancelada e o acesso terminará em{" "}
                    {format(
                      new Date(subscription.current_period_end!),
                      "dd/MM/yyyy",
                      { locale: ptBR }
                    )}
                    . Você não será cobrado novamente.
                  </AlertDescription>
                </div>
              </Alert>
            )}
          {(subscription.status === "past_due" ||
            subscription.status === "unpaid") && (
            <Alert variant="destructive">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <div className="ml-3">
                <AlertTitle className="font-semibold">
                  Problema no Pagamento
                </AlertTitle>
                <AlertDescription>
                  Não conseguimos processar seu último pagamento. Por favor,{" "}
                  <button
                    onClick={handleManageSubscription}
                    className="underline hover:text-red-700 font-semibold disabled:opacity-50 disabled:no-underline"
                    disabled={mutation.isPending}
                  >
                    atualize suas informações de pagamento
                  </button>{" "}
                  para restaurar o acesso.
                </AlertDescription>
              </div>
            </Alert>
          )}
          <Button
            onClick={handleManageSubscription}
            disabled={mutation.isPending}
            className="w-full mt-8"
            size="lg"
          >
            {mutation.isPending ? (
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            ) : (
              <Edit className="mr-2 h-5 w-5" />
            )}
            Gerenciar Assinatura e Pagamentos
            <ExternalLink className="ml-2 h-4 w-4 opacity-70" />
          </Button>
          {portalError && (
            <p className="text-sm text-red-600 mt-2 text-center">
              {portalError}
            </p>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="container mx-auto px-4 py-8 flex flex-col items-center">
      {isLoadingSubscription && (
        <div className="flex flex-col items-center text-muted-foreground py-20">
          <Loader2 className="h-12 w-12 animate-spin mb-4 text-blue-600" />
          <p className="text-lg">Carregando informações da sua assinatura...</p>
        </div>
      )}
      {/* Exibe erro apenas se não estiver carregando e houver um erro */}
      {isErrorSubscription && !isLoadingSubscription && (
        <Alert variant="destructive" className="max-w-lg w-full">
          <AlertCircle className="h-5 w-5" />
          <AlertTitle>Erro ao Carregar Assinatura</AlertTitle>
          <AlertDescription>
            {(subscriptionError as Error)?.message || // Acessa a mensagem do objeto de erro
              "Não foi possível buscar os dados da sua assinatura no momento. Tente novamente mais tarde."}
          </AlertDescription>
        </Alert>
      )}
      {/* Renderiza detalhes apenas se não estiver carregando e não houver erro */}
      {!isLoadingSubscription &&
        !isErrorSubscription &&
        renderSubscriptionDetails()}
    </div>
  );
}
