/* eslint-disable @typescript-eslint/no-explicit-any */
// src/app/dashboard/simulation/page.tsx
"use client";
import { useLayoutContext } from "@/contexts/layout-context";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"; // Import useMutation, useQueryClient
import { AlertCircle, Info, Loader2, RotateCcw } from "lucide-react"; // Import RotateCcw icon
import { useEffect, useState } from "react";
// --- UI Components ---
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

// --- Custom Hooks & API ---
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  deleteSimulationCheckpoint,
  getSimulationDetails,
} from "@/lib/api/simulation";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { toast } from "sonner";
// --- Reusable Chat Component ---
import ConversationChatView from "@/components/ui/chat/chat-view";

/**
 * Page component for the chat simulation environment.
 * Fetches simulation details (inboxId, contactId, conversationId) for the current user
 * and renders the reusable ConversationChatView component with the simulation conversation ID.
 * Includes clear visual indicators that the user is in simulation mode.
 */
export default function SimulationPage() {
  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle(
      <h1 className="text-2xl md:text-3xl tracking-tight">Modo de Simulação</h1>
    );
  }, [setPageTitle]);
  const fetcher = useAuthenticatedFetch();
  const queryClient = useQueryClient();
  // --- Query to fetch simulation details ---
  const {
    data: simulationDetails,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    // Unique query key for simulation details
    queryKey: ["simulationDetails"],
    // Call the API function using the authenticated fetcher
    queryFn: async () => {
      if (!fetcher) {
        // This state should ideally be handled by the hook/provider enabling the query later
        throw new Error("Authentication context not available.");
      }
      return getSimulationDetails(fetcher);
    },
    // Only run the query if the fetcher is ready
    enabled: !!fetcher,
    // These IDs are unlikely to change often for a user, data can be stale for longer
    staleTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false, // No need to refetch on focus usually
    retry: 1, // Retry once on failure
  });

  const [chatKey, setChatKey] = useState(Date.now()); // Estado para a chave

  // --- Mutation para Deletar Checkpoint ---
  const { mutate: resetSimulation, isPending: isResetting } = useMutation({
    mutationFn: (conversationId: string) => {
      if (!fetcher) return Promise.reject("Fetcher not available");
      // Chamar a função da API que faz o DELETE
      // Certifique-se de que a função deleteSimulationCheckpoint existe no seu api service
      return deleteSimulationCheckpoint(fetcher, conversationId);
    },
    onSuccess: () => {
      toast.success("Estado da simulação reiniciado!");
      setChatKey(Date.now());
    },
    onError: (err: any) => {
      toast.error(`Falha ao reiniciar simulação: ${err.message}`);
    },
  });

  // Handler para o botão de reset
  const handleResetClick = () => {
    if (simulationDetails?.conversation_id && !isResetting) {
      resetSimulation(simulationDetails.conversation_id);
    }
  };
  // --- Render Logic ---

  // Loading State
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="flex flex-col items-center text-muted-foreground">
          <Loader2 className="h-12 w-12 animate-spin mb-4" />
          <p>Carregando ambiente de simulação...</p>
        </div>
      </div>
    );
  }

  // Error State
  if (isError) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Alert variant="destructive" className="max-w-lg">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Erro ao Carregar Simulação</AlertTitle>
          <AlertDescription>
            Não foi possível obter os detalhes do ambiente de simulação.
            <br />
            {error instanceof Error ? error.message : "Erro desconhecido."}
            <div className="mt-4">
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                Tentar Novamente
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // Success State - Render Chat View
  if (simulationDetails) {
    return (
      // Main container for the simulation page layout
      <div className="flex flex-col h-full p-4 md:p-6 lg:p-8 space-y-4 bg-background">
        {" "}
        {/* Added bg-background */}
        {/* Page Title */}
        {/* <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">
          {" "}
          {/* Added text-foreground */}
        {/* Modo de Simulação */}
        {/* </h1> */}
        <div className="flex justify-between items-center gap-1">
          {/* Simulation Mode Alert Banner */}
          <Alert
            variant="default"
            className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800 max-w-fit"
          >
            <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <AlertTitle className="text-blue-800 dark:text-blue-300 font-semibold">
              {" "}
              {/* Added font-semibold */}
              Ambiente de Teste
            </AlertTitle>
            <AlertDescription className="text-blue-700 dark:text-blue-300">
              <span>
                Você está no modo de simulação. As mensagens enviadas aqui são
                para testar o vendedor IA e <strong>não</strong> afetam
                conversas com clientes reais.
              </span>
            </AlertDescription>
          </Alert>
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={handleResetClick}
                  disabled={isResetting || !simulationDetails?.conversation_id}
                  aria-label="Reiniciar Simulação"
                >
                  {isResetting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RotateCcw className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>Reiniciar estado da conversa (limpar memória do agente)</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        {/* Container for the Chat Component */}
        <div className="flex-grow border rounded-md overflow-hidden shadow-sm">
          {" "}
          {/* Added shadow-sm */}
          {/* Render the reusable Chat Component, passing the simulation ID */}
          <ConversationChatView
            key={chatKey}
            conversationId={simulationDetails.conversation_id}
            userDirection="in" // Define como visão do simulador (cliente)
          />
        </div>
      </div>
    );
  }

  // Fallback state (should ideally not be reached if query enabled logic is correct)
  return (
    <div className="flex items-center justify-center h-screen">
      <p className="text-muted-foreground">
        Não foi possível carregar o ambiente de simulação.
      </p>
    </div>
  );
}
