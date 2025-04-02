/**
 * @fileoverview Component for configuring the Evolution API channel.
 * Handles instance creation, QR code display, and connection status feedback via WebSocket.
 * Part of the Inbox creation wizard (Step 3).
 */
import React, { useState, useEffect, useCallback } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2, Terminal, CheckCircle, RefreshCw, WifiOff } from 'lucide-react';
import { useInboxSocket } from '@/hooks/use-evolution-inbox-socket';

// Type definitions remain in English
type ConnectionStatus = 'IDLE' | 'CREATING_INSTANCE' | 'FETCHING_QR' | 'WAITING_SCAN' | 'CONNECTED' | 'ERROR' | 'TIMEOUT' | 'SOCKET_ERROR';

interface EvolutionInstanceDetails {
    id: string;
    instance_name: string;
    // api_url might also be useful here if returned by backend
    // api_url?: string;
    // status from backend DB might differ from real-time connection status
    status?: string;
}

interface ConfigureEvolutionApiStepProps {
    inboxName: string;
    onConfigured: (details: EvolutionInstanceDetails) => void;
    onConnectionSuccess: () => void;
    onValidityChange: (isValid: boolean) => void;
    isLoading?: boolean;
}

/**
 * Renders the UI for connecting to a self-hosted Evolution API instance.
 * Used within Step 3 of the Inbox creation wizard.
 * @component
 * @param {ConfigureEvolutionApiStepProps} props - Component props.
 */
export const ConfigureEvolutionApiStep: React.FC<ConfigureEvolutionApiStepProps> = ({
    inboxName,
    onConfigured,
    onConnectionSuccess,
    onValidityChange,
    // isLoading prop might be less relevant now with detailed internal status
    // isLoading = false
}) => {
    const authenticatedFetch = useAuthenticatedFetch();
    // Expanded status to include more granular error/timeout states
    const [status, setStatus] = useState<ConnectionStatus>('IDLE');
    const [error, setError] = useState<string | null>(null);
    const [qrCode, setQrCode] = useState<string | null>(null);
    const [instanceDetails, setInstanceDetails] = useState<EvolutionInstanceDetails | null>(null);
    // Internal loading state to disable buttons during async operations
    const [isProcessing, setIsProcessing] = useState(false);

    // --- WebSocket Callbacks ---

    /** Handles successful connection via WebSocket */
    const handleConnected = useCallback(() => {
        // Check previous status to avoid unintended updates if message arrives late
        setStatus((prevStatus) => {
            if (prevStatus === 'WAITING_SCAN' || prevStatus === 'FETCHING_QR') {
                onConnectionSuccess(); // Notify parent component
                onValidityChange(true); // Mark step as valid
                return 'CONNECTED';
            }
            return prevStatus; // Ignore if not in a waiting state
        });
    }, [onConnectionSuccess, onValidityChange]);

    /** Handles timeout event via WebSocket */
    const handleTimeout = useCallback(() => {
        setStatus('TIMEOUT');
        setError("Tempo esgotado esperando a leitura do QR code. Tente atualizar o código.");
        onValidityChange(false);
        setQrCode(null); // Clear potentially expired QR code
    }, [onValidityChange]);

    /** Handles instance-specific errors reported via WebSocket */
    const handleInstanceError = useCallback((message?: string) => {
        setStatus('ERROR');
        setError(message || "Ocorreu um erro inesperado na instância.");
        onValidityChange(false);
    }, [onValidityChange]);

    /** Handles underlying WebSocket connection errors */
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const handleSocketError = useCallback((_event?: Event) => {
        setStatus('SOCKET_ERROR');
        setError("Erro de conexão com o servidor de atualizações em tempo real. Verifique sua conexão e tente novamente.");
        onValidityChange(false);
    }, [onValidityChange]);

    // --- Instantiate the WebSocket Hook ---
    useInboxSocket({
        instanceId: instanceDetails?.id,
        onConnected: handleConnected,
        onTimeout: handleTimeout,
        onInstanceError: handleInstanceError,
        onSocketError: handleSocketError,
        // onDisconnected: handleDisconnect, // Optional: handle unexpected disconnects
        onMessage: (msg) => console.log('WS Message:', msg),
    });

    // --- Async Functions ---
    const fetchQrCode = useCallback(async (details: EvolutionInstanceDetails | null) => {
        if (!details?.id) return; // Guard against missing details or id
        console.log(`Fetching QR Code for instance: ${details.id}`);
        setIsProcessing(true);
        setStatus('FETCHING_QR');
        setError(null);
        setQrCode(null);
        onValidityChange(false); // Invalid while fetching/waiting
        try {
            const response = await authenticatedFetch(`/api/v1/instances/evolution/${details.id}/qrcode`);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Falha ao buscar QR code.');
            }
            if (!data.qrcode) {
                throw new Error('QR code não recebido do backend.');
            }
            console.log("QR Code received.");
            setQrCode(data.qrcode);
            setStatus('WAITING_SCAN'); // Move to waiting state *after* getting QR code
            // Validity remains false until 'CONNECTED' message via WebSocket
        } catch (err: any) {
            console.error("Error fetching QR code:", err);
            setError(err.message || 'Erro desconhecido ao buscar QR code.');
            setStatus('ERROR');
            onValidityChange(false);
        } finally {
            setIsProcessing(false);
        }
    }, [authenticatedFetch, onValidityChange]);

    const createInstance = useCallback(async () => {
        console.log("Attempting to create Evolution instance...");
        setIsProcessing(true);
        setStatus('CREATING_INSTANCE');
        setError(null);
        setInstanceDetails(null); // Clear previous details
        setQrCode(null);
        onValidityChange(false);
        try {
            const response = await authenticatedFetch('/api/v1/instances/evolution', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data: EvolutionInstanceDetails = await response.json(); // Add type hint
            if (!response.ok) {
                throw new Error(data.detail || 'Falha ao criar instância no backend.');
            }
            // Ensure essential data is present
            if (!data.id) { 
                throw new Error('Resposta inválida (sem ID) do backend ao criar instância.');
            }
            console.log("Instance created:", data);
            setInstanceDetails(data); // Store instance details (including the ID)
            onConfigured(data); // Notify parent about the created instance config
            // Automatically fetch QR code after successful creation
            await fetchQrCode(data);

        } catch (err: any) {
            console.error("Error creating instance:", err);
            setError(err.message || 'Erro desconhecido ao criar instância.');
            setStatus('ERROR');
            onValidityChange(false);
        } finally {
             // setIsProcessing is handled by fetchQrCode if successful,
             // but needs to be set false here if creation itself fails.
             // Check status to avoid race condition if fetchQrCode already finished
             setStatus(currentStatus => {
                 if (currentStatus === 'CREATING_INSTANCE') {
                     setIsProcessing(false);
                 }
                 // If status changed (e.g., to FETCHING_QR or ERROR), keep isProcessing as is
                 // It will be handled by fetchQrCode or the error block.
                 return currentStatus;
             });
        }
    }, [authenticatedFetch, onConfigured, fetchQrCode, onValidityChange]); // Removed isLoading

    // --- Effect for Automatic Initiation ---
    useEffect(() => {
        // Automatically start the process when the component mounts
        if (status === 'IDLE') {
            createInstance();
        }
    }, [status, createInstance]); // Keep status dependency to prevent re-running if status changes for other reasons


    // --- Conditional Rendering ---
    return (
        <div className="flex flex-col items-center space-y-4 text-center">

            {/* Error, Timeout, Socket Error States */}
            {(status === 'ERROR' || status === 'TIMEOUT' || status === 'SOCKET_ERROR') && error && (
                <Alert variant="destructive" className="w-full max-w-md text-left">
                    {status === 'TIMEOUT' ? <RefreshCw className="h-4 w-4" /> : <Terminal className="h-4 w-4" />}
                    <AlertTitle>
                        {status === 'TIMEOUT' ? 'Tempo Esgotado' : 'Erro na Configuração'}
                    </AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                    {status === 'TIMEOUT' && instanceDetails ? (
                         // Button to refresh QR code on timeout
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => fetchQrCode(instanceDetails)}
                            className="mt-4"
                            disabled={isProcessing}
                        >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Atualizar QR Code
                        </Button>
                    ) : (
                         // Button to retry instance creation for other errors
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={createInstance}
                            className="mt-4"
                            disabled={isProcessing}
                        >
                            <RefreshCw className="mr-2 h-4 w-4" />
                            Tentar Novamente
                        </Button>
                    )}
                </Alert>
            )}

            {/* Loading States */}
            {(status === 'CREATING_INSTANCE' || status === 'FETCHING_QR') && (
                <>
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <p className="text-muted-foreground">
                        {status === 'CREATING_INSTANCE' ? 'Criando instância segura...' : 'Gerando QR code...'}
                    </p>
                </>
            )}

            {/* Waiting for Scan State */}
            {status === 'WAITING_SCAN' && qrCode && (
                <>
                    <h3 className="text-lg font-medium">Escaneie para Conectar</h3>
                    <p className="max-w-md text-sm text-muted-foreground">
                        Abra o WhatsApp no seu celular, vá em Aparelhos Conectados e escaneie o código abaixo.
                    </p>
                    <div className="inline-block rounded-lg bg-white p-4 shadow-md">
                        <QRCodeSVG value={qrCode} size={256} level="M" />
                    </div>
                    <p className="animate-pulse text-sm text-primary">Aguardando conexão...</p>
                    {/* Button to manually refresh QR code */}
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => instanceDetails && fetchQrCode(instanceDetails)}
                        className="mt-2"
                        disabled={isProcessing} // Use internal processing state
                    >
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Atualizar QR Code
                    </Button>
                </>
            )}

            {/* Connected State */}
            {status === 'CONNECTED' && (
                <div className="flex flex-col items-center gap-2 text-green-600">
                    <CheckCircle className="h-10 w-10" />
                    <p className="font-medium">WhatsApp Conectado com Sucesso!</p>
                    <p className="text-sm text-muted-foreground">Você pode prosseguir para o passo final.</p>
                </div>
            )}
        </div>
    );
};