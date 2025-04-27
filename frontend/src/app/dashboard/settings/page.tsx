// app/dashboard/settings/page.tsx
"use client";

import { useLayoutContext } from "@/contexts/layout-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Loader2, Terminal, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

// Internal Hooks & API Functions
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { getMyBotAgent } from "@/lib/api/bot-agent";
import { getCompanyProfile } from "@/lib/api/company-profile";
import { getResearchJobStatus } from "@/lib/api/research";
import { components } from "@/types/api";

// UI Components
import LoadingLogo from "@/components/loading-logo";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Child Page Components (already refactored)
import { CompanyResearchTrigger } from "@/components/company-research-trigger";
import { JSX } from "react/jsx-runtime";
import { BotAgentForm } from "./_components/bot-agent-form";
import { CompanyProfileForm } from "./_components/company-profile-form";

// Type definitions using generated schemas
type CompanyProfileData = components["schemas"]["CompanyProfileSchema-Output"];
type BotAgentData = components["schemas"]["BotAgentRead"];
type JobStatusEnum = components["schemas"]["ResearchJobStatusEnum"];
type ResearchJobStatusResponse =
  components["schemas"]["ResearchJobStatusResponse"];

// --- Constants ---
const PROFILE_QUERY_KEY = ["companyProfile"];
const AGENT_QUERY_KEY = ["botAgent"];
const POLLING_INTERVAL_MS = 5000; // Check job status every 5 seconds
const MAX_NOT_FOUND_RETRIES = 4; // Max retries if job is not found immediately

/**
 * Renders the main settings page, allowing users to manage their
 * Company Profile and AI Seller (Bot Agent) configurations.
 * Includes functionality to trigger AI-powered profile research and
 * displays the status of ongoing research jobs.
 * Uses React Query for data fetching and caching.
 */
export default function SettingsPage(): JSX.Element {
  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle("Configurações");
  }, [setPageTitle]);

  const fetcher = useAuthenticatedFetch();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<string>("profile");

  // --- Data Fetching with React Query ---
  const {
    data: profileData,
    isLoading: isLoadingProfile,
    isError: isErrorProfile,
    error: errorProfile,
    isFetching: isFetchingProfile, // Indicates background refetching
  } = useQuery<CompanyProfileData | null>({
    queryKey: PROFILE_QUERY_KEY,
    // Fetch profile only if fetcher is available
    queryFn: () =>
      fetcher ? getCompanyProfile(fetcher) : Promise.resolve(null),
    enabled: !!fetcher, // Only run query if fetcher is ready
    staleTime: 5 * 60 * 1000, // Data is considered fresh for 5 minutes
    refetchOnWindowFocus: false, // Avoid excessive refetches on window focus
    retry: 1, // Retry once on initial fetch error
  });

  const {
    data: agentData,
    isLoading: isLoadingAgent,
    isError: isErrorAgent,
    error: errorAgent,
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    isFetching: isFetchingAgent, // Indicates background refetching
  } = useQuery<BotAgentData | null>({
    queryKey: AGENT_QUERY_KEY,
    // Fetch agent data only if fetcher is available
    queryFn: () => (fetcher ? getMyBotAgent(fetcher) : Promise.resolve(null)),
    enabled: !!fetcher, // Only run query if fetcher is ready
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  });

  // Combined loading state for the initial page load
  const isLoadingInitial = isLoadingProfile || isLoadingAgent;
  // Combined error state for initial loading failures
  const initialLoadingError = isErrorProfile
    ? (errorProfile as Error)?.message
    : isErrorAgent
    ? (errorAgent as Error)?.message
    : null;

  // --- Research Job Polling State & Logic ---
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const [pollingStatus, setPollingStatus] = useState<JobStatusEnum | null>(
    null
  );
  const [pollingError, setPollingError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // Ref to count consecutive "not found" errors during polling
  const notFoundRetryCountRef = useRef<number>(0);

  const [isProfileDirty, setIsProfileDirty] = useState<boolean>(false);

  /**
   * Polls the backend for the status of the currently active research job.
   * Updates the polling status and handles completion or failure scenarios.
   * Stops polling when the job finishes or encounters a persistent error.
   */
  const pollJobStatus = useCallback(async () => {
    // Stop polling if fetcher or job ID is missing
    if (!fetcher || !pollingJobId) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    console.debug(`Polling status for job: ${pollingJobId}`); // Keep debug logs in English
    setPollingError(null); // Clear previous polling error

    try {
      const statusResponse: ResearchJobStatusResponse =
        await getResearchJobStatus(fetcher, pollingJobId);
      setPollingStatus(statusResponse.status);
      setPollingError(null); // Clear error on successful API call
      notFoundRetryCountRef.current = 0; // Reset counter since the job was found

      const isJobFinished = ["complete", "failed", "not_found"].includes(
        statusResponse.status
      );

      if (isJobFinished) {
        console.log(
          `Job ${pollingJobId} finished with status: ${statusResponse.status}. Stopping polling.`
        );
        // Stop the interval timer
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        const finishedJobId = pollingJobId; // Store ID before resetting state
        setPollingJobId(null); // Clear the active job ID
        setPollingStatus(null); // Reset status display

        // Handle different finished states
        if (statusResponse.status === "complete") {
          toast.success("Pesquisa Concluída!", {
            description: "O perfil da empresa foi atualizado.",
          });
          // Invalidate the profile query to trigger a refetch via React Query
          await queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEY });
          toast.info("Dados do perfil recarregados.");
        } else if (statusResponse.status === "failed") {
          const detail =
            statusResponse.detail || "Erro desconhecido durante a pesquisa.";
          toast.error("Pesquisa Falhou", { description: detail });
          setPollingError(detail); // Display failure reason in the status alert
        } else {
          // Status is 'not_found' after potentially retrying
          toast.error("Tarefa de Pesquisa Não Encontrada", {
            description: `A tarefa ${finishedJobId} não pôde mais ser encontrada.`,
          });
          setPollingError(`Tarefa ${finishedJobId} não encontrada.`);
        }
      }
      // If status is 'queued' or 'in_progress', polling continues automatically

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (error: any) {
      console.error(`Failed to poll job status for ${pollingJobId}:`, error);
      const errorMessage = error.message || "Erro desconhecido";
      const isNotFoundError =
        errorMessage.includes("Job not found") || errorMessage.includes("404");

      // Handle transient "Not Found" errors (job might not be ready immediately)
      if (
        isNotFoundError &&
        notFoundRetryCountRef.current < MAX_NOT_FOUND_RETRIES
      ) {
        notFoundRetryCountRef.current += 1;
        console.warn(
          `Job ${pollingJobId} not found yet (attempt ${notFoundRetryCountRef.current}/${MAX_NOT_FOUND_RETRIES}). Retrying...`
        );
        // Keep visual status as 'queued' or 'in_progress' to avoid flickering
        setPollingStatus((prev) =>
          prev === "in_progress" ? "in_progress" : "queued"
        );
        setPollingError(null); // Don't show error yet
      } else {
        // Handle persistent "Not Found" or other API/network errors
        console.error(
          `Stopping polling for job ${pollingJobId} due to persistent error: ${errorMessage}`
        );
        toast.error("Falha na Verificação de Status", {
          description: errorMessage,
        });
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        setPollingJobId(null); // Stop polling
        setPollingStatus("failed"); // Visually indicate failure
        setPollingError(`Falha ao obter status da tarefa: ${errorMessage}`);
        notFoundRetryCountRef.current = 0; // Reset counter
      }
    }
  }, [fetcher, pollingJobId, queryClient]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (isProfileDirty) {
        const confirmationMessage =
          "Você tem alterações não salvas. Tem certeza que deseja sair?";
        event.preventDefault();
        event.returnValue = confirmationMessage;
        return confirmationMessage;
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isProfileDirty]);

  // Effect to manage the polling interval lifecycle
  useEffect(() => {
    if (pollingJobId) {
      notFoundRetryCountRef.current = 0; // Reset retry counter when a new job starts
      // Clear any existing interval before starting a new one
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
      // Poll immediately when a job ID is set
      pollJobStatus();
      // Start the interval timer
      pollingIntervalRef.current = setInterval(
        pollJobStatus,
        POLLING_INTERVAL_MS
      );
      console.log(`Polling started for job: ${pollingJobId}`);
    } else {
      // Clear interval if pollingJobId becomes null
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
        console.log("Polling stopped.");
      }
    }
    // Cleanup function to clear interval on component unmount or before effect re-runs
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
        console.log("Polling interval cleared on cleanup.");
      }
    };
  }, [pollingJobId, pollJobStatus]);

  // --- Callbacks for Child Components ---

  /**
   * Callback triggered by CompanyResearchTrigger when a research job is started.
   * Initializes the polling state.
   * @param {string | null} jobId - The ID of the started job, or null if starting failed.
   */
  const handleResearchStarted = useCallback((jobId: string | null) => {
    if (jobId) {
      console.log(
        `Research started with Job ID: ${jobId}. Initiating polling.`
      );
      setPollingJobId(jobId);
      setPollingStatus("queued"); // Set initial visual status
      setPollingError(null);
      setIsProfileDirty(false);
      notFoundRetryCountRef.current = 0; // Reset retries for the new job
    } else {
      console.error("Research task failed to start.");
      // Ensure polling state is cleared if starting fails
      setPollingJobId(null);
      setPollingStatus(null);
      setPollingError("Falha ao iniciar a tarefa de pesquisa."); // Provide feedback
    }
  }, []); // No dependencies needed as it only sets state

  /**
   * Callback triggered by CompanyProfileForm after a successful manual save.
   * Updates the React Query cache with the new profile data.
   * @param {CompanyProfileData} updatedProfile - The updated company profile data.
   */
  const handleProfileUpdate = useCallback(
    (updatedProfile: CompanyProfileData) => {
      // Manually update the query cache to reflect the changes immediately
      queryClient.setQueryData(PROFILE_QUERY_KEY, updatedProfile);
      console.log("Profile cache updated after manual save.");
    },
    [queryClient] // Depends on queryClient
  );

  /**
   * Callback triggered by BotAgentForm after a successful manual save.
   * Updates the React Query cache with the new agent data.
   * @param {BotAgentData} updatedAgent - The updated bot agent data.
   */
  const handleAgentUpdate = useCallback(
    (updatedAgent: BotAgentData) => {
      // Manually update the query cache
      queryClient.setQueryData(AGENT_QUERY_KEY, updatedAgent);
      console.log("Agent cache updated after manual save.");
      // Optionally invalidate related queries if needed, e.g., agent's associated inboxes
      // queryClient.invalidateQueries({ queryKey: ['agentInboxes', updatedAgent.id] });
    },
    [queryClient] // Depends on queryClient
  );

  // --- Render Helper Functions ---

  /** Renders a loading indicator for the initial page load. */
  const renderLoading = () => (
    <div className="flex justify-center items-center p-10 min-h-[300px]">
      <LoadingLogo />
    </div>
  );

  /** Renders an error message if initial data fetching fails. */
  const renderError = () => (
    <Alert variant="destructive" className="mt-4">
      <Terminal className="h-4 w-4" />
      <AlertTitle>Erro ao Carregar Configurações</AlertTitle>
      <AlertDescription>
        {initialLoadingError || "Ocorreu um erro desconhecido."}
      </AlertDescription>
    </Alert>
  );

  // Determine if research is actively running (to disable forms/triggers)
  const isResearching =
    pollingJobId !== null &&
    pollingStatus !== "failed" &&
    pollingStatus !== "not_found" &&
    pollingStatus !== "complete"; // Consider 'complete' as not actively researching

  // --- Main Component Render ---
  // --- Main Component Render ---
  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8 space-y-6">
      {/* Research Status Area - Displayed only when pollingJobId is active */}
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
            <XCircle className="h-4 w-4" /> // Show XCircle for pollingError too
          ) : (
            <Terminal className="h-4 w-4" /> // Default icon
          )}
          <AlertTitle>
            {pollingStatus === "in_progress"
              ? "Pesquisa em Andamento..."
              : pollingStatus === "queued"
              ? "Pesquisa na Fila..."
              : pollingStatus === "complete"
              ? "Pesquisa Concluída"
              : pollingStatus === "failed" || pollingError // Show failed title also for pollingError
              ? "Falha na Pesquisa"
              : "Verificando Status da Pesquisa..."}
          </AlertTitle>
          <AlertDescription>
            {pollingError
              ? pollingError // Display specific error if polling failed
              : pollingStatus === "complete"
              ? `Tarefa ${pollingJobId} concluída com sucesso.`
              : `Rastreando tarefa: ${pollingJobId}. O status atualiza automaticamente.`}
          </AlertDescription>
        </Alert>
      )}

      {/* Main Content Area (Loading, Error, or Tabs) */}
      {isLoadingInitial ? (
        renderLoading() // Show initial loading state
      ) : initialLoadingError ? (
        renderError() // Show initial error state
      ) : (
        // Wrapper for Tabs navigation and conditional content display
        <div className="w-full mt-0">
          {/* Tabs component now only handles the navigation triggers */}
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full" // No margin needed here if wrapper has it
          >
            <TabsList className="grid w-full grid-cols-2 md:max-w-[450px]">
              <TabsTrigger value="profile">Perfil da Empresa</TabsTrigger>
              <TabsTrigger value="agent">Vendedor IA</TabsTrigger>
            </TabsList>
            {/* No TabsContent here */}
          </Tabs>

          {/* Container for the actual tab contents, rendered outside Tabs component */}
          <div className="mt-6">
            {" "}
            {/* Add margin top for spacing below TabsList */}
            {/* Content for the 'profile' tab */}
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
            {/* Content for the 'agent' tab */}
            <div className={`${activeTab !== "agent" ? "hidden" : ""}`}>
              <BotAgentForm
                initialAgentData={agentData ?? null}
                fetcher={fetcher!}
                onAgentUpdate={handleAgentUpdate}
                // Optionally disable agent form while profile is researching/refetching
                // disabled={isResearching || isFetchingProfile || isFetchingAgent}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
