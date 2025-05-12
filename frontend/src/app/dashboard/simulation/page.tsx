/* eslint-disable @typescript-eslint/no-explicit-any */
// src/app/dashboard/simulation/page.tsx
"use client";
import { useLayoutContext } from "@/contexts/layout-context";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  BotMessageSquare,
  Info,
  Loader2,
  RotateCcw,
  Settings,
} from "lucide-react"; // Added Settings, BotMessageSquare
import Link from "next/link"; // Added Link for navigation
import { useEffect, useState } from "react";

// --- UI Components ---
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"; // Added Card components

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

// Constants for error messages
const AGENT_NOT_CREATED_ERROR_SUBSTRING = "Crie seu agente"; // Substring from backend error

/**
 * Page component for the chat simulation environment.
 * Fetches simulation details and renders the chat view.
 * Provides guidance if the simulation environment isn't fully set up (e.g., Bot Agent not created).
 */
export default function SimulationPage() {
  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle(
      <h1 className="text-2xl md:text-3xl tracking-tight">Modo de Simulação</h1>
    );
  }, [setPageTitle]);

  const fetcher = useAuthenticatedFetch();
  const [chatKey, setChatKey] = useState(Date.now());

  const {
    data: simulationDetails,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["simulationDetails"],
    queryFn: async () => {
      if (!fetcher) {
        throw new Error("Authentication context not available.");
      }
      return getSimulationDetails(fetcher);
    },
    enabled: !!fetcher,
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: (failureCount, error: any) => {
      // Do not retry automatically if the error is about agent not being created
      if (error?.message?.includes(AGENT_NOT_CREATED_ERROR_SUBSTRING)) {
        return false;
      }
      return failureCount < 1; // Default retry once for other errors
    },
  });

  const { mutate: resetSimulation, isPending: isResetting } = useMutation({
    mutationFn: (conversationId: string) => {
      if (!fetcher) return Promise.reject("Fetcher not available");
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

  const handleResetClick = () => {
    if (simulationDetails?.conversation_id && !isResetting) {
      resetSimulation(simulationDetails.conversation_id);
    }
  };

  // --- Render Logic ---

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-150px)]">
        {" "}
        {/* Adjusted height for better centering */}
        <div className="flex flex-col items-center text-muted-foreground">
          <Loader2 className="h-12 w-12 animate-spin mb-4" />
          <p>Carregando ambiente de simulação...</p>
        </div>
      </div>
    );
  }

  if (isError) {
    const errorMessage =
      error instanceof Error ? error.message : "Erro desconhecido.";
    const isAgentNotCreatedError = errorMessage.includes(
      AGENT_NOT_CREATED_ERROR_SUBSTRING
    );

    if (isAgentNotCreatedError) {
      return (
        <div className="flex items-center justify-center h-[calc(100vh-200px)] p-4">
          <Card className="w-full max-w-lg text-center">
            <CardHeader>
              <div className="mx-auto bg-primary/10 p-3 rounded-full w-fit mb-3">
                <BotMessageSquare className="h-10 w-10 text-primary" />
              </div>
              <CardTitle>Vendedor IA ainda não está pronto</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center space-y-4">
              <p className="text-sm text-muted-foreground">
                Para usar o ambiente de simulação, primeiro você precisa
                configurar seu vendedor IA.
              </p>
              <Link href="/dashboard/settings" passHref legacyBehavior>
                <Button asChild size="lg">
                  <a>
                    <Settings className="mr-2 h-5 w-5" />
                    Ir para Configurações
                  </a>
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      );
    }

    // Generic error display
    return (
      <div className="flex items-center justify-center h-[calc(100vh-150px)] p-4">
        <Alert variant="destructive" className="max-w-lg">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Erro ao Carregar Simulação</AlertTitle>
          <AlertDescription>
            Não foi possível obter os detalhes do ambiente de simulação.
            <br />
            {errorMessage}
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

  if (simulationDetails) {
    return (
      <div className="flex flex-col h-full p-4 md:p-6 lg:p-8 space-y-4 bg-background">
        <div className="flex justify-between items-center gap-1">
          <Alert
            variant="default"
            className="bg-blue-50 border-blue-200 dark:bg-blue-950 dark:border-blue-800 max-w-fit"
          >
            <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <AlertTitle className="text-blue-800 dark:text-blue-300 font-semibold">
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
        <div className="flex-grow border rounded-md overflow-hidden shadow-sm">
          <ConversationChatView
            key={chatKey}
            conversationId={simulationDetails.conversation_id}
            userDirection="in"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center h-screen">
      <p className="text-muted-foreground">
        Não foi possível carregar o ambiente de simulação. Verifique sua conexão
        ou tente novamente mais tarde.
      </p>
    </div>
  );
}
