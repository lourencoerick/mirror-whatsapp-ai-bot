// src/app/billing/plans/page.tsx
"use client";

import { Plan, PlanCard } from "@/components/ui/billing/plan-card"; // Ajuste o caminho se necessário
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
} from "@/config/billing-plans"; // Importa todos os planos e o plano beta
import { useLayoutContext } from "@/contexts/layout-context"; // Para setPageTitle
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
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

export default function BillingPlansPage() {
  const { setPageTitle } = useLayoutContext();
  const { isSignedIn, isLoaded: isClerkLoaded } = useUser();
  const fetcher = useAuthenticatedFetch();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [pageApiError, setPageApiError] = useState<string | null>(null);

  // Estado para o status da solicitação beta do usuário
  const [userBetaStatus, setUserBetaStatus] = useState<
    AppBetaStatusEnumType | "not_found" | "loading" | "error" | null
  >("loading");
  // Estado para controlar se a checagem inicial do status beta foi feita
  const [initialBetaStatusCheckComplete, setInitialBetaStatusCheckComplete] =
    useState(false);

  useEffect(() => {
    setPageTitle?.("Nossos Planos");
  }, [setPageTitle]);

  // Efeito para exibir toast de confirmação de solicitação beta
  useEffect(() => {
    if (searchParams.get("beta_request_submitted") === "true") {
      toast.success("Solicitação Recebida!", {
        description:
          "Sua solicitação para o programa beta foi enviada com sucesso. Entraremos em contato em breve.",
      });
      // Limpa o query param para não mostrar o toast novamente no refresh/navegação
      router.replace("/billing/plans", { scroll: false });
    }
  }, [searchParams, router]);

  // Efeito para buscar o status beta do usuário
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
          setUserBetaStatus("error"); // Estado de erro específico para a busca do beta status
          toast.error("Erro ao verificar status Beta", {
            description: errorMsg,
          });
        } finally {
          setInitialBetaStatusCheckComplete(true);
        }
      };
      fetchBetaStatus();
    } else if (isClerkLoaded && !isSignedIn) {
      // Se o Clerk carregou mas não está logado, não há status beta para buscar
      setUserBetaStatus(null); // Ou 'not_applicable'
      setInitialBetaStatusCheckComplete(true);
    } else if (!isClerkLoaded) {
      // Ainda aguardando Clerk carregar
      setUserBetaStatus("loading");
    }
  }, [isClerkLoaded, isSignedIn, fetcher, initialBetaStatusCheckComplete]);

  // Callback para erros vindos do PlanCard
  const handlePlanCardError = (errorMessage: string) => {
    if (errorMessage) {
      setPageApiError(errorMessage); // Define o erro global da página
      // O toast de erro já é mostrado dentro do PlanCard, não precisa duplicar aqui
    } else {
      setPageApiError(null);
    }
  };

  // Lógica para determinar quais planos exibir
  const displayedPlans = useMemo((): Plan[] => {
    if (!initialBetaStatusCheckComplete || userBetaStatus === "loading") {
      return []; // Não mostra planos enquanto o status beta estiver carregando
    }

    const betaPlan = getBetaPlan(); // Pega o plano beta da configuração

    // Se o usuário for aprovado para o beta, mostrar APENAS o plano beta (ou conforme sua regra de negócio)
    if (userBetaStatus === AppBetaStatusEnum.APPROVED && betaPlan) {
      // Você pode querer destacar ou adicionar um texto especial ao plano beta aqui
      return [
        {
          ...betaPlan,
          highlight: true,
          buttonText: "Ativar Acesso Beta Gratuito",
        },
      ];
    }

    // Se não estiver aprovado para o beta (ou não houver plano beta), mostrar planos pagos normais
    // Filtra para não mostrar o plano beta na lista de planos pagos se ele já foi tratado
    return allAvailablePlans.filter((plan) => !plan.isBeta);
  }, [userBetaStatus, initialBetaStatusCheckComplete]);

  // Seção para solicitar acesso beta ou mostrar status da solicitação
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
      // Se aprovado, o plano beta já estará em displayedPlans, não precisa de CTA aqui.
      // Mas podemos colocar uma mensagem de boas-vindas.
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

    // Se 'not_found', 'denied', 'error', ou null (não logado e Clerk carregado)
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

  // Handler para quando nenhum plano é selecionado/aplicável
  const renderNoPlansAvailable = () => {
    // Esta mensagem aparece se, após toda a lógica, displayedPlans estiver vazio.
    // Isso pode acontecer se o usuário não for beta aprovado E não houver planos pagos configurados.
    // Ou se houver um erro ao carregar o status beta e não pudermos determinar os planos.
    if (userBetaStatus === "loading" || !initialBetaStatusCheckComplete) {
      return null; // O loader principal já está tratando isso
    }
    if (userBetaStatus === "error") {
      return (
        <p className="text-center text-red-500 text-lg mt-8">
          Não foi possível carregar os planos devido a um erro ao verificar seu
          status beta.
        </p>
      );
    }
    // Se o beta está pendente, a mensagem já está no renderBetaCallToActionSection
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

      {/* Seção de Chamada para Ação Beta */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
        {renderBetaCallToActionSection()}
      </div>

      {/* Loader principal enquanto o status beta é verificado E não há planos para mostrar ainda */}
      {userBetaStatus === "loading" &&
        !initialBetaStatusCheckComplete &&
        displayedPlans.length === 0 && (
          <div className="text-center py-10">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-600" />{" "}
            <p>Carregando planos...</p>
          </div>
        )}

      {/* Renderiza os PlanCards */}
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
              // onSubscribe é gerenciado internamente pelo PlanCard
              onSubscriptionError={handlePlanCardError}
              // O PlanCard gerencia seu próprio isLoading para o botão.
              // isDisabledByParent é para desabilitar o botão por razões externas (ex: beta não aprovado, mas aqui já filtramos)
              // Se o plano beta é o único exibido, ele já foi verificado como 'APPROVED'
              isDisabledByParent={
                plan.isBeta && userBetaStatus !== AppBetaStatusEnum.APPROVED
              }
            />
          ))}
        </div>
      ) : (
        // Só mostra "nenhum plano" se a checagem inicial foi feita e não está carregando
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
  );
}
