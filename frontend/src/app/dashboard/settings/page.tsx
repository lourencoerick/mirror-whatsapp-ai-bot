/* eslint-disable @typescript-eslint/no-explicit-any */
// app/dashboard/settings/page.tsx
"use client";

import { useLayoutContext } from "@/contexts/layout-context";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BotMessageSquare,
  CheckCircle,
  Edit3,
  Loader2,
  Sparkles,
  Terminal,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

// Internal Hooks & API Functions
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { createMyBotAgent, getMyBotAgent } from "@/lib/api/bot-agent";
import { getCompanyProfile } from "@/lib/api/company-profile";
import { getResearchJobStatus } from "@/lib/api/research";
import { components } from "@/types/api";

// UI Components
import LoadingLogo from "@/components/loading-logo";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Child Page Components
import { CompanyResearchTrigger } from "@/components/company-research-trigger";
import { JSX } from "react/jsx-runtime";
import { BotAgentForm } from "./_components/bot-agent-form";
import { CompanyProfileForm } from "./_components/company-profile-form";

// Type definitions using generated schemas
type CompanyProfileData = components["schemas"]["CompanyProfileSchema-Output"];
type BotAgentData = components["schemas"]["BotAgentRead"];
type BotAgentCreateData = components["schemas"]["BotAgentCreate"];
type JobStatusEnum = components["schemas"]["ResearchJobStatusEnum"];
type ResearchJobStatusResponse =
  components["schemas"]["ResearchJobStatusResponse"];

// --- Constants ---
const PROFILE_QUERY_KEY = ["companyProfile"];
const AGENT_QUERY_KEY = ["botAgent"];
const POLLING_INTERVAL_MS = 5000;
const MAX_NOT_FOUND_RETRIES = 4;

const AGENT_CREATION_STEPS = [
  "Preparando para criar seu vendedor...",
  "Definindo a personalidade do vendedor...",
  "Ensinando técnicas de vendas avançadas...",
  "Conectando à sua caixa de entrada principal...",
  "Quase pronto! Finalizando configurações...",
];
const AGENT_CREATION_STEP_DURATION = 2000;
const MIN_TOTAL_CREATION_DISPLAY_TIME =
  AGENT_CREATION_STEPS.length * AGENT_CREATION_STEP_DURATION;

const DEFAULT_AGENT_NAME = "Assistente Principal";
const DEFAULT_AGENT_FIRST_MESSAGE = null;
const DEFAULT_AGENT_USE_RAG = true;

/**
 * Renders the main settings page, allowing users to manage their
 * Company Profile and AI Seller (Bot Agent) configurations.
 */
export default function SettingsPage(): JSX.Element {
  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle(
      <h1 className="text-2xl md:text-3xl tracking-tight">Configurações</h1>
    );
  }, [setPageTitle]);

  const fetcher = useAuthenticatedFetch();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<string>("profile");
  const [newAgentName, setNewAgentName] = useState<string>(DEFAULT_AGENT_NAME);

  const {
    data: profileData,
    isLoading: isLoadingProfile,
    isError: isErrorProfile,
    error: errorProfile,
    isFetching: isFetchingProfile,
  } = useQuery<CompanyProfileData | null>({
    queryKey: PROFILE_QUERY_KEY,
    queryFn: () =>
      fetcher ? getCompanyProfile(fetcher) : Promise.resolve(null),
    enabled: !!fetcher,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  const {
    data: agentData,
    isLoading: isLoadingAgentInitial,
    isError: isErrorAgent,
    error: errorAgent,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    isFetching: isFetchingAgent,
  } = useQuery<BotAgentData | null>({
    queryKey: AGENT_QUERY_KEY,
    queryFn: () => (fetcher ? getMyBotAgent(fetcher) : Promise.resolve(null)),
    enabled: !!fetcher,
    staleTime: 1 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: (failureCount, error: any) => {
      if (error?.message?.includes("No Bot Agent found")) {
        return false;
      }
      return failureCount < 1;
    },
  });

  const isLoadingInitial = isLoadingProfile || isLoadingAgentInitial;
  const initialLoadingError = isErrorProfile
    ? (errorProfile as Error)?.message
    : isErrorAgent
    ? (errorAgent as Error)?.message
    : null;

  const [creationStepMessage, setCreationStepMessage] = useState<string>("");
  const [creationCurrentStep, setCreationCurrentStep] = useState<number>(0);
  const creationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const apiCallStartTimestampRef = useRef<number>(0);

  const agentCreationMutation = useMutation<
    BotAgentData,
    Error,
    BotAgentCreateData
  >({
    mutationFn: async (data: BotAgentCreateData) => {
      if (!fetcher) throw new Error("Fetcher not available");

      apiCallStartTimestampRef.current = Date.now();
      let newAgent: BotAgentData | undefined;
      let visualStepsCompleted = false;

      // Start visual steps interval
      const stepsDisplayPromise = new Promise<void>((resolveSteps) => {
        let currentStepForInterval = 0;
        // Initial message set in onMutate, here we just update state for progress bar
        setCreationCurrentStep(currentStepForInterval);

        if (creationIntervalRef.current)
          clearInterval(creationIntervalRef.current);
        creationIntervalRef.current = setInterval(() => {
          currentStepForInterval++;
          setCreationCurrentStep(currentStepForInterval);
          if (currentStepForInterval < AGENT_CREATION_STEPS.length) {
            setCreationStepMessage(
              AGENT_CREATION_STEPS[currentStepForInterval]
            );
          } else {
            if (creationIntervalRef.current)
              clearInterval(creationIntervalRef.current);
            creationIntervalRef.current = null;
            visualStepsCompleted = true;
            resolveSteps();
          }
        }, AGENT_CREATION_STEP_DURATION);
      });

      try {
        // Perform API call
        newAgent = await createMyBotAgent(fetcher, data);

        // Wait for visual steps to complete if API finished first
        if (!visualStepsCompleted) {
          await stepsDisplayPromise;
        }

        // Ensure minimum display time after API success and visual steps completion
        const elapsedTime = Date.now() - apiCallStartTimestampRef.current;
        const remainingTime = MIN_TOTAL_CREATION_DISPLAY_TIME - elapsedTime;
        if (remainingTime > 0) {
          await new Promise((resolveDelay) =>
            setTimeout(resolveDelay, remainingTime)
          );
        }

        if (!newAgent) {
          // Should not happen if createMyBotAgent resolves correctly
          throw new Error("Agent creation succeeded but returned no data.");
        }
        return newAgent;
      } catch (error) {
        // If API call fails, clear interval and re-throw to be caught by onError
        if (creationIntervalRef.current) {
          clearInterval(creationIntervalRef.current);
          creationIntervalRef.current = null;
        }
        // Ensure visualStepsCompleted is true so we don't try to await stepsDisplayPromise again if error occurs
        visualStepsCompleted = true;
        throw error; // Re-throw the original error
      }
    },
    onMutate: () => {
      setCreationCurrentStep(0);
      setCreationStepMessage(AGENT_CREATION_STEPS[0]);
    },
    onSuccess: (newAgentData) => {
      toast.success("Vendedor IA Criado!", {
        description: `${
          newAgentData.name || DEFAULT_AGENT_NAME
        } está pronto para começar.`,
      });
      queryClient.setQueryData(AGENT_QUERY_KEY, newAgentData);
      queryClient.invalidateQueries({ queryKey: AGENT_QUERY_KEY });
      setActiveTab("agent");
      setNewAgentName(DEFAULT_AGENT_NAME);
      setCreationStepMessage(""); // Clear message
      // Interval should be cleared by mutationFn or onSettled
    },
    onError: (error: Error) => {
      toast.error("Falha ao Criar Vendedor IA", {
        description: error.message || "Ocorreu um erro desconhecido.",
      });
      setCreationStepMessage(""); // Clear message
      // Interval should be cleared by mutationFn or onSettled
    },
    onSettled: () => {
      setCreationCurrentStep(0); // Reset step for progress bar
      if (creationIntervalRef.current) {
        clearInterval(creationIntervalRef.current);
        creationIntervalRef.current = null;
      }
    },
  });

  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const [pollingStatus, setPollingStatus] = useState<JobStatusEnum | null>(
    null
  );
  const [pollingError, setPollingError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const notFoundRetryCountRef = useRef<number>(0);
  const [isProfileDirty, setIsProfileDirty] = useState<boolean>(false);

  const pollJobStatus = useCallback(async () => {
    if (!fetcher || !pollingJobId) {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      return;
    }
    setPollingError(null);
    try {
      const statusResponse: ResearchJobStatusResponse =
        await getResearchJobStatus(fetcher, pollingJobId);
      setPollingStatus(statusResponse.status);
      notFoundRetryCountRef.current = 0;
      const isJobFinished = ["complete", "failed", "not_found"].includes(
        statusResponse.status
      );
      if (isJobFinished) {
        if (pollingIntervalRef.current)
          clearInterval(pollingIntervalRef.current);
        const finishedJobId = pollingJobId;
        setPollingJobId(null);
        setPollingStatus(null);
        if (statusResponse.status === "complete") {
          toast.success("Pesquisa Concluída!", {
            description: "O perfil da empresa foi atualizado.",
          });
          await queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEY });
        } else if (statusResponse.status === "failed") {
          const detail =
            statusResponse.detail || "Erro desconhecido durante a pesquisa.";
          toast.error("Pesquisa Falhou", { description: detail });
          setPollingError(detail);
        } else {
          toast.error("Tarefa de Pesquisa Não Encontrada", {
            description: `A tarefa ${finishedJobId} não pôde mais ser encontrada.`,
          });
          setPollingError(`Tarefa ${finishedJobId} não encontrada.`);
        }
      }
    } catch (error: any) {
      const errorMessage = error.message || "Erro desconhecido";
      const isNotFoundError =
        errorMessage.includes("Job not found") || errorMessage.includes("404");
      if (
        isNotFoundError &&
        notFoundRetryCountRef.current < MAX_NOT_FOUND_RETRIES
      ) {
        notFoundRetryCountRef.current += 1;
        setPollingStatus((prev) =>
          prev === "in_progress" ? "in_progress" : "queued"
        );
        setPollingError(null);
      } else {
        toast.error("Falha na Verificação de Status", {
          description: errorMessage,
        });
        if (pollingIntervalRef.current)
          clearInterval(pollingIntervalRef.current);
        setPollingJobId(null);
        setPollingStatus("failed");
        setPollingError(`Falha ao obter status da tarefa: ${errorMessage}`);
        notFoundRetryCountRef.current = 0;
      }
    }
  }, [fetcher, pollingJobId, queryClient]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (isProfileDirty) {
        event.preventDefault();
        event.returnValue =
          "Você tem alterações não salvas. Tem certeza que deseja sair?";
        return event.returnValue;
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isProfileDirty]);

  useEffect(() => {
    if (pollingJobId) {
      notFoundRetryCountRef.current = 0;
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      pollJobStatus();
      pollingIntervalRef.current = setInterval(
        pollJobStatus,
        POLLING_INTERVAL_MS
      );
    } else {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }
    // Cleanup for intervals on component unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      if (creationIntervalRef.current) {
        clearInterval(creationIntervalRef.current);
        creationIntervalRef.current = null;
      }
    };
  }, [pollingJobId, pollJobStatus]);

  const handleResearchStarted = useCallback((jobId: string | null) => {
    if (jobId) {
      setPollingJobId(jobId);
      setPollingStatus("queued");
      setPollingError(null);
      setIsProfileDirty(false);
      notFoundRetryCountRef.current = 0;
    } else {
      setPollingJobId(null);
      setPollingStatus(null);
      setPollingError("Falha ao iniciar a tarefa de pesquisa.");
    }
  }, []);

  const handleProfileUpdate = useCallback(
    (updatedProfile: CompanyProfileData) => {
      queryClient.setQueryData(PROFILE_QUERY_KEY, updatedProfile);
    },
    [queryClient]
  );

  const handleAgentUpdate = useCallback(
    (updatedAgent: BotAgentData) => {
      queryClient.setQueryData(AGENT_QUERY_KEY, updatedAgent);
    },
    [queryClient]
  );

  const handleCreateAgent = () => {
    const trimmedName = newAgentName.trim();
    if (!trimmedName) {
      toast.error("Nome Inválido", {
        description: "Por favor, forneça um nome para o seu vendedor IA.",
      });
      return;
    }
    const agentPayload: BotAgentCreateData = {
      name: trimmedName,
      first_message: DEFAULT_AGENT_FIRST_MESSAGE,
      use_rag: DEFAULT_AGENT_USE_RAG,
    };
    agentCreationMutation.mutate(agentPayload);
  };

  const renderLoading = () => (
    <div className="flex justify-center items-center p-10 min-h-[300px]">
      <LoadingLogo />
    </div>
  );

  const renderError = () => (
    <Alert variant="destructive" className="mt-4">
      <Terminal className="h-4 w-4" />
      <AlertTitle>Erro ao Carregar Configurações</AlertTitle>
      <AlertDescription>
        {initialLoadingError || "Ocorreu um erro desconhecido."}
      </AlertDescription>
    </Alert>
  );

  const isResearching =
    pollingJobId !== null &&
    pollingStatus !== "failed" &&
    pollingStatus !== "not_found" &&
    pollingStatus !== "complete";

  const renderAgentCreationArea = (): JSX.Element | null => {
    if (
      agentData ||
      isLoadingAgentInitial ||
      agentCreationMutation.isPending ||
      agentCreationMutation.isError
    ) {
      return null;
    }
    const agentQueryError = errorAgent as Error | null;
    if (
      agentQueryError &&
      !agentQueryError.message?.includes("No Bot Agent found") &&
      !agentCreationMutation.isPending
    ) {
      return (
        <Alert variant="destructive" className="mt-4">
          <XCircle className="h-4 w-4" />
          <AlertTitle>Erro ao Verificar Vendedor IA</AlertTitle>
          <AlertDescription>
            {agentQueryError.message ||
              "Não foi possível verificar a existência de um vendedor IA."}
            <Button
              variant="link"
              onClick={() =>
                queryClient.invalidateQueries({ queryKey: AGENT_QUERY_KEY })
              }
              className="p-0 h-auto ml-2"
            >
              Tentar novamente
            </Button>
          </AlertDescription>
        </Alert>
      );
    }
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center">
            <BotMessageSquare className="mr-2 h-6 w-6 text-primary" />
            Configure seu Vendedor IA
          </CardTitle>
          <CardDescription>
            Dê um nome ao seu vendedor IA e inicie a configuração para
            automatizar suas vendas!
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <Label htmlFor="new-agent-name" className="mb-1.5 block">
              <Edit3 className="inline-block mr-2 h-4 w-4" />
              Nome do Vendedor IA
            </Label>
            <Input
              id="new-agent-name"
              type="text"
              value={newAgentName}
              onChange={(e) => setNewAgentName(e.target.value)}
              placeholder="Ex: Assistente de Vendas Pro"
              disabled={agentCreationMutation.isPending}
              maxLength={255}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Este será o nome exibido para o seu assistente.
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            Ao clicar no botão abaixo, seu assistente virtual será preparado com
            as melhores técnicas de vendas e conectado aos seus canais.
          </p>
          <Button
            onClick={handleCreateAgent}
            disabled={
              agentCreationMutation.isPending ||
              !fetcher ||
              !newAgentName.trim()
            }
            size="lg"
            className="w-full md:w-auto"
          >
            <Sparkles className="mr-2 h-5 w-5" />
            Criar Meu Vendedor IA
          </Button>
        </CardContent>
      </Card>
    );
  };

  const renderAgentCreationProgress = () => {
    // Show progress if pending
    if (agentCreationMutation.isPending) {
      const progressPercentage = Math.min(
        ((creationCurrentStep + 1) / AGENT_CREATION_STEPS.length) * 100,
        100
      );
      return (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center">
              <Loader2 className="mr-2 h-6 w-6 animate-spin text-primary" />
              Criando seu Vendedor IA...
            </CardTitle>
            <CardDescription>
              Por favor, aguarde enquanto preparamos tudo para você. Isso pode
              levar alguns instantes.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="w-full bg-muted rounded-full h-2.5">
              <div
                className="bg-primary h-2.5 rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progressPercentage}%` }}
              ></div>
            </div>
            <p className="text-center text-sm text-muted-foreground h-10 flex items-center justify-center">
              {creationStepMessage || AGENT_CREATION_STEPS[0]}
            </p>
          </CardContent>
        </Card>
      );
    }

    // Show error state if mutation failed
    if (agentCreationMutation.isError) {
      return (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="flex items-center text-destructive">
              <XCircle className="mr-2 h-6 w-6" />
              Falha na Criação do Vendedor IA
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="destructive" className="mt-0">
              <XCircle className="h-4 w-4" />
              <AlertTitle>Erro Detalhado</AlertTitle>
              <AlertDescription>
                {agentCreationMutation.error?.message ||
                  "Ocorreu um erro inesperado."}
              </AlertDescription>
            </Alert>
            <Button
              onClick={() => {
                agentCreationMutation.reset(); // Reset mutation state
                // Optionally reset other relevant states like newAgentName if needed
                setNewAgentName(DEFAULT_AGENT_NAME);
                setCreationStepMessage(""); // Clear any lingering message
                setCreationCurrentStep(0);
              }}
              className="w-full"
              variant="outline"
            >
              Tentar Novamente
            </Button>
          </CardContent>
        </Card>
      );
    }
    return null; // Don't render if not pending and not error
  };

  const isAgentTabDisabled = isLoadingAgentInitial && !agentData;

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8 space-y-6">
      {pollingJobId && (
        <Alert
          variant={
            pollingStatus === "failed" || pollingError
              ? "destructive"
              : "default"
          }
          className="mt-4"
        >
          {pollingStatus === "in_progress" || pollingStatus === "queued" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : pollingStatus === "complete" ? (
            <CheckCircle className="h-4 w-4 text-green-600" />
          ) : pollingStatus === "failed" || pollingError ? (
            <XCircle className="h-4 w-4" />
          ) : (
            <Terminal className="h-4 w-4" />
          )}
          <AlertTitle>
            {pollingStatus === "in_progress"
              ? "Pesquisa em Andamento..."
              : pollingStatus === "queued"
              ? "Pesquisa na Fila..."
              : pollingStatus === "complete"
              ? "Pesquisa Concluída"
              : pollingStatus === "failed" || pollingError
              ? "Falha na Pesquisa"
              : "Verificando Status da Pesquisa..."}
          </AlertTitle>
          <AlertDescription>
            {pollingError
              ? pollingError
              : pollingStatus === "complete"
              ? `Tarefa ${pollingJobId} concluída com sucesso.`
              : `Rastreando tarefa: ${pollingJobId}. O status atualiza automaticamente.`}
          </AlertDescription>
        </Alert>
      )}

      {isLoadingInitial && !initialLoadingError ? (
        renderLoading()
      ) : initialLoadingError &&
        !initialLoadingError.includes("No Bot Agent found") ? (
        renderError()
      ) : (
        <div className="w-full mt-0">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <TabsList className="grid w-full grid-cols-2 md:max-w-[450px]">
              <TabsTrigger value="profile">Perfil da Empresa</TabsTrigger>
              <TabsTrigger value="agent" disabled={isAgentTabDisabled}>
                Vendedor IA
              </TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="mt-6">
            <div
              className={`space-y-6 ${activeTab !== "profile" ? "hidden" : ""}`}
            >
              <CompanyResearchTrigger
                fetcher={fetcher!}
                profileExists={profileData != null}
                disabled={isResearching || !fetcher || isFetchingProfile}
                onResearchStarted={handleResearchStarted}
              />
              <CompanyProfileForm
                initialData={profileData ?? null}
                fetcher={fetcher!}
                onProfileUpdate={handleProfileUpdate}
                isResearching={isResearching || isFetchingProfile}
                onDirtyChange={setIsProfileDirty}
              />
            </div>

            <div className={`${activeTab !== "agent" ? "hidden" : ""}`}>
              {/* Render progress OR error from mutation */}
              {(agentCreationMutation.isPending ||
                agentCreationMutation.isError) &&
                renderAgentCreationProgress()}

              {/* Render creation area only if no agent, not loading, not pending, and no error from mutation */}
              {!agentData &&
                !isLoadingAgentInitial &&
                !agentCreationMutation.isPending &&
                !agentCreationMutation.isError &&
                renderAgentCreationArea()}

              {/* Render form if agent exists and not pending mutation */}
              {agentData && !agentCreationMutation.isPending && (
                <BotAgentForm
                  initialAgentData={agentData}
                  fetcher={fetcher!}
                  onAgentUpdate={handleAgentUpdate}
                />
              )}

              {/* Initial loading indicator for agent tab */}
              {isLoadingAgentInitial &&
                !agentData &&
                !agentCreationMutation.isPending &&
                !agentCreationMutation.isError && // also don't show if mutation error is displayed
                activeTab === "agent" && (
                  <Card className="mt-6">
                    <CardHeader>
                      <CardTitle>Carregando Vendedor IA...</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <LoadingLogo />
                    </CardContent>
                  </Card>
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
