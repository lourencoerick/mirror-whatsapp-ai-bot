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
  const [creationCurrentStepState, setCreationCurrentStepState] =
    useState<number>(0); // Renamed to avoid conflict
  const creationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const apiCallTimestampRef = useRef<number>(0);

  const agentCreationMutation = useMutation({
    mutationFn: async (data: BotAgentCreateData) => {
      if (!fetcher) throw new Error("Fetcher not available");

      apiCallTimestampRef.current = Date.now();
      const agentPromise = createMyBotAgent(fetcher, data);

      // This ref will hold the latest step reached by the interval
      // to be accessible by the delay logic after Promise.all
      const currentVisualStepRef = { current: 0 };

      const stepsDisplayPromise = new Promise<void>((resolveStepsDisplay) => {
        // Local currentStep for this promise's interval
        let stepForInterval = 0;
        setCreationStepMessage(AGENT_CREATION_STEPS[stepForInterval]);
        setCreationCurrentStepState(stepForInterval); // Update state for progress bar
        currentVisualStepRef.current = stepForInterval;

        if (creationIntervalRef.current)
          clearInterval(creationIntervalRef.current);
        creationIntervalRef.current = setInterval(() => {
          stepForInterval++;
          setCreationCurrentStepState(stepForInterval); // Update state for progress bar
          currentVisualStepRef.current = stepForInterval;

          if (stepForInterval < AGENT_CREATION_STEPS.length) {
            setCreationStepMessage(AGENT_CREATION_STEPS[stepForInterval]);
          } else {
            if (creationIntervalRef.current)
              clearInterval(creationIntervalRef.current);
            creationIntervalRef.current = null; // Explicitly nullify
            resolveStepsDisplay();
          }
        }, AGENT_CREATION_STEP_DURATION);
      });

      // Wait for both the API call to finish AND the visual steps to complete (or API to fail)
      let newAgent: BotAgentData | undefined;
      let apiError: Error | undefined;

      try {
        // Wait for both promises. If agentPromise rejects, Promise.all will reject.
        [newAgent] = await Promise.all([agentPromise, stepsDisplayPromise]);
      } catch (err) {
        apiError = err as Error;
        // If API failed, we still want to ensure the steps interval is cleared
        if (creationIntervalRef.current) {
          clearInterval(creationIntervalRef.current);
          creationIntervalRef.current = null;
        }
        // We don't wait for stepsDisplayPromise to complete if API fails.
        // The error will be thrown and handled by onError.
        throw apiError;
      }

      // If API finished very fast AND all steps were displayed, ensure we wait for the minimum display time
      const elapsedTime = Date.now() - apiCallTimestampRef.current;
      const remainingTime = MIN_TOTAL_CREATION_DISPLAY_TIME - elapsedTime;

      // Only add delay if API was successful, all steps were shown, and there's remaining time
      if (
        newAgent &&
        currentVisualStepRef.current >= AGENT_CREATION_STEPS.length - 1 &&
        remainingTime > 0
      ) {
        await new Promise((resolveDelay) =>
          setTimeout(resolveDelay, remainingTime)
        );
      }

      if (!newAgent && !apiError) {
        // This case should ideally not be reached if agentPromise resolves with data or rejects
        throw new Error(
          "Agent creation did not return data and did not error."
        );
      }

      return newAgent as BotAgentData; // newAgent could be undefined if API failed and was caught by outer try/catch
    },
    onMutate: () => {
      setCreationCurrentStepState(0); // Use the renamed state setter
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
      setCreationStepMessage("");
      if (creationIntervalRef.current) {
        clearInterval(creationIntervalRef.current);
        creationIntervalRef.current = null;
      }
    },
    onError: (error: Error) => {
      toast.error("Falha ao Criar Vendedor IA", {
        description: error.message || "Ocorreu um erro desconhecido.",
      });
      setCreationStepMessage("");
      if (creationIntervalRef.current) {
        clearInterval(creationIntervalRef.current);
        creationIntervalRef.current = null;
      }
    },
    onSettled: () => {
      setCreationCurrentStepState(0); // Use the renamed state setter
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
    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      if (creationIntervalRef.current)
        clearInterval(creationIntervalRef.current);
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
    const agentPayload: BotAgentCreateData = { name: trimmedName };
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
    if (agentData || isLoadingAgentInitial || agentCreationMutation.isPending) {
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
    if (!agentCreationMutation.isPending) return null;
    // Use creationCurrentStepState for the progress bar percentage
    const progressPercentage = Math.min(
      ((creationCurrentStepState + 1) / AGENT_CREATION_STEPS.length) * 100,
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
          {agentCreationMutation.isError && (
            <Alert variant="destructive">
              <XCircle className="h-4 w-4" />
              <AlertTitle>Falha na Criação</AlertTitle>
              <AlertDescription>
                {(agentCreationMutation.error as Error)?.message ||
                  "Ocorreu um erro inesperado."}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    );
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
              {renderAgentCreationProgress()}
              {!agentData &&
                !agentCreationMutation.isPending &&
                !isLoadingAgentInitial &&
                renderAgentCreationArea()}
              {agentData && !agentCreationMutation.isPending && (
                <BotAgentForm
                  initialAgentData={agentData}
                  fetcher={fetcher!}
                  onAgentUpdate={handleAgentUpdate}
                />
              )}
              {isLoadingAgentInitial &&
                !agentData &&
                !agentCreationMutation.isPending &&
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
