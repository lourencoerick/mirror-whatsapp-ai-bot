// src/app/beta/status/page.tsx
"use client";

import { Plan, PlanCard } from "@/components/ui/billing/plan-card";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getBetaPlan } from "@/config/billing-plans";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { AppBetaStatusEnum, BetaTesterStatusResponse } from "@/lib/enums";
import {
  AlertTriangle,
  CheckCircle,
  Loader2,
  MailCheck,
  RefreshCw,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

type AppBetaStatusValue =
  (typeof AppBetaStatusEnum)[keyof typeof AppBetaStatusEnum];

export default function BetaStatusPage() {
  const { setPageTitle } = useLayoutContext();
  const router = useRouter();
  const fetcher = useAuthenticatedFetch();

  const [currentStatus, setCurrentStatus] = useState<
    AppBetaStatusValue | null | "loading" | "not_found" | "error"
  >("loading");
  const [requestedAt, setRequestedAt] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [betaPlanDetails, setBetaPlanDetails] = useState<Plan | undefined>(
    undefined
  );
  const [isRefreshingStatus, setIsRefreshingStatus] = useState(false);

  useEffect(() => {
    setPageTitle?.("Status da sua Solicitação Beta");
    setBetaPlanDetails(getBetaPlan());
  }, [setPageTitle]);

  const fetchUserBetaStatus = useCallback(
    async (isButtonRefresh: boolean = false) => {
      if (!fetcher) {
        const errorMsg =
          "Serviço de autenticação não está pronto para buscar status.";
        console.warn("BetaStatusPage:", errorMsg);
        if (isButtonRefresh) {
          toast.error("Erro de Autenticação", { description: errorMsg });
        } else {
          setCurrentStatus("error");
          setApiError(errorMsg);
        }
        return;
      }

      if (isButtonRefresh) {
        setIsRefreshingStatus(true);
      } else {
        setCurrentStatus("loading");
      }
      if (!isButtonRefresh) setApiError(null);

      try {
        const response = await fetcher("/api/v1/beta/my-status");
        if (!response.ok) {
          if (response.status === 404) {
            setCurrentStatus("not_found");
          } else {
            const errorData = await response.json().catch(() => ({
              detail: "Erro desconhecido ao processar resposta.",
            }));
            throw new Error(
              errorData.detail || `Erro ${response.status} ao buscar status.`
            );
          }
        } else {
          const data: BetaTesterStatusResponse = await response.json();
          if (
            data.status &&
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            Object.values(AppBetaStatusEnum).includes(data.status as any)
          ) {
            setCurrentStatus(data.status as AppBetaStatusValue);
          } else {
            setCurrentStatus("not_found");
          }
          if (data.requested_at) {
            setRequestedAt(
              new Date(data.requested_at).toLocaleDateString("pt-BR", {
                day: "2-digit",
                month: "long",
                year: "numeric",
              })
            );
          }
          // Limpar erro da API em caso de sucesso, mesmo que seja refresh do botão
          setApiError(null);
        }
      } catch (err) {
        const errorMsg =
          err instanceof Error
            ? err.message
            : "Não foi possível carregar seu status.";
        console.error("Erro ao buscar status beta na página de status:", err);
        setApiError(errorMsg);
        if (!isButtonRefresh) {
          setCurrentStatus(null); // Indica erro no estado principal apenas na carga inicial
        }
        // Mostrar toast de erro em ambos os casos (carga inicial ou refresh do botão)
        toast.error("Falha ao Buscar Status", { description: errorMsg });
      } finally {
        if (isButtonRefresh) {
          setIsRefreshingStatus(false);
        }
        // Se não for refresh do botão e o status ainda for 'loading' (ex: fetcher se tornou null no meio),
        // pode ser necessário um estado de erro mais explícito.
        // Mas a lógica atual deve cobrir a maioria dos casos.
      }
    },
    [fetcher]
  );

  useEffect(() => {
    // Busca inicial quando o fetcher estiver disponível
    fetchUserBetaStatus(false);
  }, [fetcher, fetchUserBetaStatus]); // Adicionado fetchUserBetaStatus como dependência

  const handlePlanCardError = (errorMessage: string) => {
    if (errorMessage) {
      toast.error("Erro na Assinatura Beta", { description: errorMessage });
    }
  };

  const renderContent = () => {
    // Loader principal da página (quando currentStatus é 'loading' E não é um refresh de botão)
    if (currentStatus === "loading" && !isRefreshingStatus) {
      return (
        <div className="flex flex-col items-center justify-center py-10">
          <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
          <p className="mt-4 text-lg text-muted-foreground">
            Verificando status da sua solicitação...
          </p>
        </div>
      );
    }

    // Erro na carga inicial (currentStatus === null devido a erro E não é refresh de botão)
    if (apiError && currentStatus === null && !isRefreshingStatus) {
      return (
        <div className="text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-red-500" />
          <h2 className="mt-4 text-2xl font-semibold">
            Erro ao Carregar Status
          </h2>
          <p className="mt-2 text-muted-foreground">
            {apiError ||
              "Não foi possível verificar o status da sua solicitação no momento."}
          </p>
          <Button
            onClick={() => fetchUserBetaStatus(false)}
            className="mt-6 inline-flex items-center"
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Tentar Novamente
          </Button>
        </div>
      );
    }

    if (currentStatus === "not_found") {
      return (
        <div className="text-center">
          <XCircle className="mx-auto h-12 w-12 text-gray-400" />
          <h2 className="mt-4 text-2xl font-semibold">
            Nenhuma Solicitação Encontrada
          </h2>
          <p className="mt-2 text-muted-foreground">
            Parece que você ainda não solicitou acesso ao nosso programa beta.
          </p>
          <Button asChild className="mt-6">
            <Link href="/beta/apply">Inscrever-se no Beta</Link>
          </Button>
        </div>
      );
    }

    if (currentStatus === AppBetaStatusEnum.PENDING_APPROVAL) {
      return (
        <div className="text-center">
          <MailCheck className="mx-auto h-12 w-12 text-blue-600" />
          <h2 className="mt-4 text-2xl font-semibold">
            Solicitação em Análise!
          </h2>
          <p className="mt-2 text-muted-foreground">
            Recebemos sua solicitação para o programa beta em{" "}
            <span className="font-medium">
              {requestedAt || "data não disponível"}
            </span>
            . Nossa equipe está analisando e entraremos em contato por email.
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Obrigado pelo seu interesse!
          </p>
          <Button
            onClick={() => fetchUserBetaStatus(true)} // Passa true para indicar refresh do botão
            className="mt-8 inline-flex items-center space-x-2"
            variant="outline"
            disabled={isRefreshingStatus}
          >
            {isRefreshingStatus ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            <span>
              {isRefreshingStatus ? "Verificando..." : "Verificar Atualização"}
            </span>
          </Button>
        </div>
      );
    }

    if (currentStatus === AppBetaStatusEnum.APPROVED) {
      if (!betaPlanDetails) {
        return (
          <div className="text-center">
            <AlertTriangle className="mx-auto h-12 w-12 text-yellow-500" />
            <h2 className="mt-4 text-2xl font-semibold">
              Plano Beta Não Configurado
            </h2>
            <p className="mt-2 text-muted-foreground">
              Seu acesso foi aprovado, mas não conseguimos carregar os detalhes
              do plano beta. Por favor, contate o suporte.
            </p>
          </div>
        );
      }
      return (
        <div className="text-center space-y-8">
          <div>
            <CheckCircle className="mx-auto h-12 w-12 text-green-500" />
            <h2 className="mt-4 text-2xl font-semibold">
              Acesso Beta Aprovado!
            </h2>
            <p className="mt-2 text-muted-foreground max-w-md mx-auto">
              Parabéns! Sua solicitação para o programa beta foi aprovada.
              Clique abaixo para ativar seu acesso gratuito e começar a explorar
              todas as funcionalidades.
            </p>
          </div>
          <div className="max-w-sm mx-auto">
            <PlanCard
              plan={betaPlanDetails}
              onSubscriptionError={handlePlanCardError}
            />
          </div>
          {/* <Button
            variant="link"
            onClick={() => router.push("/billing/plans")}
            className="text-sm text-gray-600 hover:text-blue-600"
          >
            Ver outros planos disponíveis
          </Button> */}
        </div>
      );
    }

    if (currentStatus === AppBetaStatusEnum.DENIED) {
      return (
        <div className="text-center">
          <XCircle className="mx-auto h-12 w-12 text-red-500" />
          <h2 className="mt-4 text-2xl font-semibold">
            Solicitação Não Aprovada
          </h2>
          <p className="mt-2 text-muted-foreground">
            Agradecemos seu interesse, mas no momento não podemos aprovar sua
            solicitação para o programa beta. Em breve você poderá explorar
            nossos planos pagos.
          </p>
          <Button asChild className="mt-6">
            <Link href="/billing/plans">Ver Planos Pagos</Link>
          </Button>
        </div>
      );
    }

    console.warn(
      `BetaStatusPage: Status desconhecido ou não mapeado recebido: ${currentStatus}`
    );
    return (
      <div className="text-center">
        <AlertTriangle className="mx-auto h-12 w-12 text-yellow-500" />
        <h2 className="mt-4 text-2xl font-semibold">
          Status da Solicitação Indisponível
        </h2>
        <p className="mt-2 text-muted-foreground">
          Não foi possível determinar o status exato da sua solicitação no
          momento. Por favor, tente novamente mais tarde ou{" "}
          <Link href="/contato" className="underline text-blue-600">
            contate o suporte
          </Link>
          .
        </p>
        <Button onClick={() => router.push("/dashboard")} className="mt-6">
          Voltar ao Dashboard
        </Button>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-xl">
        <Card className="bg-white shadow-xl">
          <CardHeader>
            <CardTitle className="text-center text-2xl font-semibold text-gray-800">
              Status da sua Inscrição Beta
            </CardTitle>
            {currentStatus !== "loading" &&
              currentStatus !== "not_found" &&
              currentStatus !== null && (
                <CardDescription className="text-center text-sm text-gray-500 pt-1">
                  {currentStatus === AppBetaStatusEnum.PENDING_APPROVAL &&
                    `Sua solicitação foi feita em: ${requestedAt || "N/A"}`}
                  {currentStatus === AppBetaStatusEnum.APPROVED &&
                    "Tudo pronto para você começar!"}
                  {currentStatus === AppBetaStatusEnum.DENIED &&
                    "Agradecemos o seu interesse em nosso programa."}
                </CardDescription>
              )}
          </CardHeader>
          <CardContent className="pt-6 pb-8 px-6 md:px-8">
            {renderContent()}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
