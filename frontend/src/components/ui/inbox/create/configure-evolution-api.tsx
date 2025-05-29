/* eslint-disable @typescript-eslint/no-unused-vars */
// src/components/ui/inbox/new/configure-evolution-api.tsx
/**
 * @fileoverview Component for configuring the Evolution API channel.
 * Handles instance creation OR connection for an existing instance,
 * QR code display, and connection status feedback via WebSocket.
 */
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { useInboxSocket } from "@/hooks/use-evolution-inbox-socket"; // Ensure correct path
import {
  CheckCircle,
  Loader2,
  RefreshCw,
  Terminal,
  WifiOff,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import React, { useCallback, useEffect, useState } from "react";

import { Event as RwsEvent } from "reconnecting-websocket";
// Type definitions
type ConnectionStatus =
  | "IDLE"
  | "CREATING_INSTANCE"
  | "FETCHING_QR"
  | "WAITING_SCAN"
  | "CONNECTED"
  | "ERROR"
  | "TIMEOUT"
  | "SOCKET_ERROR";

interface EvolutionInstanceDetails {
  id: string; // Instance ID from backend (e.g., Evolution's instanceName or a UUID)
  instance_name?: string; // Optional: Name if provided by backend
  shared_api_url?: string; // Optional: URL if provided
  logical_token_encrypted?: string; // Optional: Token if provided
  status?: string; // Optional: Status from backend DB
}

interface ConfigureEvolutionApiStepProps {
  inboxName?: string; // Optional for editing context
  existingInstanceId?: string | null; // *** NEW: ID of the instance if editing ***
  onConfigured?: (details: EvolutionInstanceDetails) => void; // Optional for editing
  onConnectionSuccess: () => void; // Still useful for feedback
  onValidityChange?: (isValid: boolean) => void; // Optional for editing, indicates connection status
  onStatusChange?: (status: ConnectionStatus, error?: string | null) => void; // *** NEW: More granular status reporting ***
  isLoading?: boolean; // Optional: Loading state for parent component
}

/**
 * Renders the UI for connecting to an Evolution API instance.
 * Can be used during creation or for reconnecting an existing inbox.
 * @component
 */
export const ConfigureEvolutionApiStep: React.FC<
  ConfigureEvolutionApiStepProps
> = ({
  inboxName, // Used only during creation for potential naming consistency
  existingInstanceId = null, // Default to null
  onConfigured,
  onConnectionSuccess,
  onValidityChange,
  onStatusChange,
}) => {
  const authenticatedFetch = useAuthenticatedFetch();
  const [status, setStatus] = useState<ConnectionStatus>("IDLE");
  const [error, setError] = useState<string | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [instanceDetails, setInstanceDetails] =
    useState<EvolutionInstanceDetails | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // --- Status Update Helper ---
  // Centralize status updates to also call onStatusChange prop
  const updateStatus = useCallback(
    (newStatus: ConnectionStatus, errorMsg: string | null = null) => {
      setStatus(newStatus);
      setError(errorMsg);
      if (onStatusChange) {
        onStatusChange(newStatus, errorMsg);
      }
      // Update validity based on status
      if (onValidityChange) {
        onValidityChange(newStatus === "CONNECTED");
      }
    },
    [onStatusChange, onValidityChange]
  );

  // --- WebSocket Callbacks (using updateStatus) ---
  const handleConnected = useCallback(() => {
    setStatus((prevStatus) => {
      if (prevStatus === "WAITING_SCAN" || prevStatus === "FETCHING_QR") {
        onConnectionSuccess();
        updateStatus("CONNECTED");
        return "CONNECTED"; // Return new status for setStatus
      }
      return prevStatus;
    });
  }, [onConnectionSuccess, updateStatus]);

  const handleTimeout = useCallback(() => {
    const msg =
      "Tempo esgotado esperando a leitura do QR code. Tente atualizar o código.";
    updateStatus("TIMEOUT", msg);
    setQrCode(null);
  }, [updateStatus]);

  const handleInstanceError = useCallback(
    (message?: string) => {
      const msg = message || "Ocorreu um erro inesperado na instância.";
      updateStatus("ERROR", msg);
    },
    [updateStatus]
  );

  const handleSocketError = useCallback(
    (_event?: RwsEvent) => {
      const msg =
        "Erro de conexão com o servidor de atualizações. Verifique sua conexão.";
      updateStatus("SOCKET_ERROR", msg);
    },
    [updateStatus]
  );

  // --- Instantiate WebSocket Hook ---
  useInboxSocket({
    instanceId: instanceDetails?.id, // Use the ID from state
    onConnected: handleConnected,
    onTimeout: handleTimeout,
    onInstanceError: handleInstanceError,
    onSocketError: handleSocketError,
    onMessage: (msg) => console.log("WS Message:", msg),
  });

  // --- Async Functions ---
  const fetchQrCode = useCallback(
    async (details: EvolutionInstanceDetails | null) => {
      if (!details?.id) {
        updateStatus(
          "ERROR",
          "ID da instância não encontrado para buscar QR code."
        );
        return;
      }
      console.log(`Fetching QR Code for instance: ${details.id}`);
      setIsProcessing(true);
      updateStatus("FETCHING_QR");
      setQrCode(null);

      try {
        // *** IMPORTANT: Ensure this endpoint matches your backend route ***
        const response = await authenticatedFetch(
          `/api/v1/instances/evolution/${details.id}/qrcode`
        );
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || "Falha ao buscar QR code.");
        }
        if (!data.qrcode) {
          throw new Error("QR code não recebido do backend.");
        }
        console.log("QR Code received.");
        setQrCode(data.qrcode);
        updateStatus("WAITING_SCAN"); // Move to waiting state
      } catch (err: unknown) {
        console.error("Error fetching QR code:", err);
        const errorMsg =
          err instanceof Error
            ? err.message
            : "Erro desconhecido ao buscar QR code.";
        updateStatus("ERROR", errorMsg);
      } finally {
        setIsProcessing(false);
      }
    },
    [authenticatedFetch, updateStatus]
  );

  const createInstance = useCallback(async () => {
    console.log("Attempting to create Evolution instance...");
    setIsProcessing(true);
    updateStatus("CREATING_INSTANCE");
    setInstanceDetails(null);
    setQrCode(null);

    try {
      // *** IMPORTANT: Ensure this endpoint matches your backend route ***
      const response = await authenticatedFetch("/api/v1/instances/evolution", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Optionally pass inboxName if backend uses it during creation
        // body: JSON.stringify({ suggested_name: inboxName })
      });
      const data: EvolutionInstanceDetails = await response.json();
      if (!response.ok) {
        throw new Error("Falha ao criar instância no backend.");
      }
      if (!data.id) {
        throw new Error("Resposta inválida (sem ID) do backend.");
      }
      console.log("Instance created:", data);
      setInstanceDetails(data);
      if (onConfigured) {
        // Call only if provided (creation flow)
        onConfigured(data);
      }
      await fetchQrCode(data); // Fetch QR after creation
    } catch (err: unknown) {
      console.error("Error creating instance:", err);
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Erro desconhecido ao criar instância.";
      updateStatus("ERROR", errorMessage);
      // Ensure processing stops if creation fails before fetchQrCode starts
      setIsProcessing(false);
    }

    // No finally block needed here for setIsProcessing, as fetchQrCode handles it
  }, [authenticatedFetch, onConfigured, fetchQrCode, updateStatus]); // Removed inboxName dependency unless used in body

  // --- Effect for Automatic Initiation (Modified) ---
  useEffect(() => {
    // Only run when component mounts and status is IDLE
    if (status === "IDLE") {
      if (existingInstanceId) {
        // --- Editing Existing Instance ---
        console.log(
          `[ConfigureEvolutionApiStep] Using existing instance ID: ${existingInstanceId}`
        );
        // Set minimal details needed to proceed (just the ID)
        const initialDetails: EvolutionInstanceDetails = {
          id: existingInstanceId,
        };
        setInstanceDetails(initialDetails);
        // Directly fetch the QR code, don't create instance
        fetchQrCode(initialDetails);
      } else {
        // --- Creating New Instance ---
        createInstance();
      }
    }
    // Intentionally run only once on mount based on initial IDLE status and props
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingInstanceId]); // Dependencies ensure it runs if ID changes, but logic prevents re-run if status isn't IDLE

  // --- Render Logic (Remains largely the same, uses internal 'status') ---
  return (
    <div className="flex flex-col items-center space-y-4 text-center p-4 border rounded-lg bg-muted/30">
      {/* Error, Timeout, Socket Error States */}
      {(status === "ERROR" ||
        status === "TIMEOUT" ||
        status === "SOCKET_ERROR") &&
        error && (
          <Alert variant="destructive" className="w-full max-w-md text-left">
            {/* Icon based on status */}
            {status === "TIMEOUT" && <RefreshCw className="h-4 w-4" />}
            {status === "SOCKET_ERROR" && <WifiOff className="h-4 w-4" />}
            {status === "ERROR" && <Terminal className="h-4 w-4" />}

            <AlertTitle>
              {status === "TIMEOUT"
                ? "Tempo Esgotado"
                : status === "SOCKET_ERROR"
                ? "Erro de Conexão"
                : "Erro na Configuração"}
            </AlertTitle>
            <AlertDescription>{error}</AlertDescription>

            {/* Action Button: Refresh QR or Retry Creation */}
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                instanceDetails
                  ? fetchQrCode(instanceDetails)
                  : createInstance()
              }
              disabled={isProcessing}
              className="mt-4 inline-flex items-center gap-2 whitespace-nowra min-w-max"
            >
              <RefreshCw className="h-4 w-4" />
              <span>Atualizar QR Code</span>
            </Button>
          </Alert>
        )}

      {/* Loading States */}
      {(status === "CREATING_INSTANCE" || status === "FETCHING_QR") && (
        <>
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">
            {status === "CREATING_INSTANCE"
              ? "Criando instância..."
              : "Gerando QR code..."}
          </p>
        </>
      )}

      {/* Waiting for Scan State */}
      {status === "WAITING_SCAN" && qrCode && (
        <>
          <h3 className="text-lg font-medium">Escaneie para Conectar</h3>
          <p className="max-w-md text-sm text-muted-foreground">
            Abra o WhatsApp no seu celular, vá em Aparelhos Conectados e
            escaneie o código abaixo.
          </p>
          <div className="inline-block rounded-lg bg-white p-4 shadow-md">
            <QRCodeSVG value={qrCode} size={220} level="M" />{" "}
            {/* Slightly smaller size */}
          </div>
          <p className="animate-pulse text-sm text-primary">
            Aguardando conexão...
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => instanceDetails && fetchQrCode(instanceDetails)}
            className="mt-2"
            disabled={isProcessing}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Atualizar QR Code
          </Button>
        </>
      )}

      {/* Connected State */}
      {status === "CONNECTED" && (
        <div className="flex flex-col items-center gap-2 text-green-600">
          <CheckCircle className="h-10 w-10" />
          <p className="font-medium">WhatsApp Conectado!</p>
          <p className="text-sm text-muted-foreground">
            A conexão foi estabelecida.
          </p>
        </div>
      )}
    </div>
  );
};
