// src/app/billing/plans/page.tsx
"use client";

import { PlanCard } from "@/components/ui/billing/plan-card";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  plansData as allAvailablePlans,
  getBetaPlan,
} from "@/config/billing-plans";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  AppBetaStatusEnum,
  AppBetaStatusEnumType,
  BetaTesterStatusResponse,
} from "@/lib/enums";
import { useUser } from "@clerk/nextjs";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { toast } from "sonner";

function BetaRequestListener() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    if (searchParams.get("beta_request_submitted") === "true") {
      toast.success("Solicitação Recebida!", {
        description:
          "Sua solicitação para o programa beta foi enviada com sucesso. Entraremos em contato em breve.",
      });
      router.replace("/billing/plans", { scroll: false });
    }
  }, [searchParams, router]);

  return null;
}

export default function BillingPlansPage() {
  const { setPageTitle } = useLayoutContext();
  const { isSignedIn, isLoaded: isClerkLoaded } = useUser();
  const fetcher = useAuthenticatedFetch();
  const router = useRouter();

  const [pageApiError, setPageApiError] = useState<string | null>(null);
  const [userBetaStatus, setUserBetaStatus] = useState<
    AppBetaStatusEnumType | "not_found" | "loading" | "error" | null
  >("loading");
  const [initialBetaStatusCheckComplete, setInitialBetaStatusCheckComplete] =
    useState(false);

  useEffect(() => {
    setPageTitle?.("Nossos Planos");
  }, [setPageTitle]);

  useEffect(() => {
    if (
      isClerkLoaded &&
      isSignedIn &&
      fetcher &&
      !initialBetaStatusCheckComplete
    ) {
      const fetchBetaStatus = async () => {
        setUserBetaStatus("loading");
        setPageApiError(null);
        try {
          const response = await fetcher("/api/v1/beta/my-status");
          if (!response.ok) {
            if (response.status === 404) setUserBetaStatus("not_found");
            else {
              const errorData = await response
                .json()
                .catch(() => ({ detail: "Erro desconhecido" }));
              throw new Error(
                errorData.detail ||
                  `Erro ${response.status} ao buscar status beta.`
              );
            }
          } else {
            const data: BetaTesterStatusResponse = await response.json();
            setUserBetaStatus(data.status || "not_found");
          }
        } catch (err) {
          const errorMsg =
            err instanceof Error ? err.message : "Falha ao buscar status beta.";
          setPageApiError(errorMsg);
          setUserBetaStatus("error");
          toast.error("Erro ao verificar status Beta", {
            description: errorMsg,
          });
        } finally {
          setInitialBetaStatusCheckComplete(true);
        }
      };
      fetchBetaStatus();
    } else if (isClerkLoaded && !isSignedIn) {
      setUserBetaStatus(null);
      setInitialBetaStatusCheckComplete(true);
    } else if (!isClerkLoaded) {
      setUserBetaStatus("loading");
    }
  }, [isClerkLoaded, isSignedIn, fetcher, initialBetaStatusCheckComplete]);

  const handlePlanCardError = (errorMessage: string) => {
    setPageApiError(errorMessage || null);
  };

  const displayedPlans = (() => {
    if (!initialBetaStatusCheckComplete || userBetaStatus === "loading") {
      return [];
    }
    const betaPlan = getBetaPlan();
    if (userBetaStatus === AppBetaStatusEnum.APPROVED && betaPlan) {
      return [
        {
          ...betaPlan,
          highlight: true,
          buttonText: "Ativar Acesso Beta Gratuito",
        },
      ];
    }
    return allAvailablePlans.filter((plan) => !plan.isBeta);
  })();

  const renderBetaCallToActionSection = () => {
    if (
      !isSignedIn ||
      !initialBetaStatusCheckComplete ||
      userBetaStatus === "loading"
    ) {
      return (
        <div className="text-center py-6">
          <Loader2 className="h-6 w-6 animate-spin mx-auto" />
        </div>
      );
    }
    if (userBetaStatus === AppBetaStatusEnum.APPROVED) {
      return (
        <div className="mb-8 text-center col-span-1 md:col-span-2 lg:col-span-3">
          <h2 className="text-2xl font-semibold text-green-600">
            Parabéns, seu acesso Beta foi aprovado!
          </h2>
          <p className="text-muted-foreground">
            O plano Beta está disponível abaixo para você ativar.
          </p>
        </div>
      );
    }
    if (userBetaStatus === AppBetaStatusEnum.PENDING_APPROVAL) {
      return (
        <Card className="mb-8 bg-blue-50 border-blue-200 col-span-1 md:col-span-2 lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-blue-700">
              Solicitação Beta em Análise
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-blue-600">
              Sua solicitação para o programa beta está sendo analisada.
              Avisaremos por email assim que houver uma atualização!
            </p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => router.push("/beta/status")}
            >
              Ver Status da Solicitação
            </Button>
          </CardContent>
        </Card>
      );
    }
    return (
      <Card className="mb-8 col-span-1 md:col-span-2 lg:col-span-3 bg-gradient-to-r from-blue-500 to-indigo-600 text-white">
        <CardHeader>
          <CardTitle className="text-3xl">
            Transforme seu WhatsApp em uma Máquina de Vendas!
          </CardTitle>
          <CardDescription className="text-blue-100 mt-2 text-lg">
            Lambda Labs está oferecendo acesso antecipado para empresas
            selecionadas. Inscreva-se para ter a chance de testar gratuitamente
            nossa Inteligência Artificial.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <Link href="/beta/apply">
            <Button
              className="bg-white text-blue-600 hover:bg-blue-50 font-semibold py-3 px-6 text-lg"
              size="lg"
            >
              Quero Participar do Beta!
            </Button>
          </Link>
        </CardContent>
      </Card>
    );
  };

  const renderNoPlansAvailable = () => {
    if (userBetaStatus === "loading" || !initialBetaStatusCheckComplete) {
      return null;
    }
    if (userBetaStatus === "error") {
      return (
        <p className="text-center text-red-500 text-lg mt-8">
          Não foi possível carregar os planos devido a um erro ao verificar seu
          status beta.
        </p>
      );
    }
    if (userBetaStatus === AppBetaStatusEnum.PENDING_APPROVAL) return null;
    return (
      <div className="text-center text-muted-foreground text-lg mt-10 col-span-1 md:col-span-2 lg:col-span-3">
        <p>Nenhum plano de assinatura disponível para você no momento.</p>
        {userBetaStatus === "not_found" && (
          <p>
            Considere{" "}
            <Link href="/beta/apply" className="text-blue-600 hover:underline">
              solicitar acesso ao nosso programa beta
            </Link>
            .
          </p>
        )}
        <p className="mt-2">
          Se você acredita que isso é um erro, por favor,{" "}
          <Link href="/support" className="text-blue-600 hover:underline">
            contate o suporte
          </Link>
          .
        </p>
      </div>
    );
  };

  return (
    <>
      <Suspense fallback={null}>
        <BetaRequestListener />
      </Suspense>

      <div className="container mx-auto px-4 py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-extrabold tracking-tight text-gray-900 sm:text-5xl">
            Nossos Planos
          </h1>
          <p className="mt-4 max-w-2xl mx-auto text-xl text-gray-500">
            Escolha a opção que melhor se adapta às suas necessidades e comece a
            vender mais hoje mesmo.
          </p>
        </div>

        {pageApiError && (
          <div className="mb-6 p-4 text-red-700 bg-red-100 border border-red-400 rounded text-center">
            <p>
              <strong>Erro:</strong> {pageApiError}
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
          {renderBetaCallToActionSection()}
        </div>

        {userBetaStatus === "loading" &&
          !initialBetaStatusCheckComplete &&
          displayedPlans.length === 0 && (
            <div className="text-center py-10">
              <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-600" />{" "}
              <p>Carregando planos...</p>
            </div>
          )}

        {displayedPlans.length > 0 ? (
          <div
            className={`grid grid-cols-1 gap-8 ${
              displayedPlans.length > 1 ? "md:grid-cols-2" : ""
            } ${
              displayedPlans.length >= 3
                ? "lg:grid-cols-3"
                : displayedPlans.length === 2
                ? "lg:grid-cols-2 lg:max-w-4xl lg:mx-auto"
                : "lg:max-w-md lg:mx-auto"
            }`}
          >
            {displayedPlans.map((plan) => (
              <PlanCard
                key={plan.id}
                plan={plan}
                onSubscriptionError={handlePlanCardError}
                isDisabledByParent={
                  plan.isBeta && userBetaStatus !== AppBetaStatusEnum.APPROVED
                }
              />
            ))}
          </div>
        ) : (
          initialBetaStatusCheckComplete &&
          userBetaStatus !== "loading" &&
          renderNoPlansAvailable()
        )}

        <p className="mt-12 text-center text-sm text-gray-500">
          Os pagamentos são processados de forma segura pelo Stripe. Dúvidas?{" "}
          <Link href="/support" className="text-blue-600 hover:underline">
            Fale conosco
          </Link>
          .
        </p>
      </div>
    </>
  );
}
