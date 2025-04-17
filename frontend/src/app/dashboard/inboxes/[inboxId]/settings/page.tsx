/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch'; // Ajuste o caminho se necessário
import { useLayoutContext } from '@/contexts/layout-context'; // Ajuste o caminho se necessário
// UPDATE: Corrected type names and added ConversationStatusOption
import { Inbox, InboxUpdatePayload, ConversationStatusOption } from '@/types/inbox'; // Ajuste o caminho se necessário
import { EvolutionInstanceStatus } from '@/types/evolution-instance'; // Ajuste o caminho se necessário
import * as evolutionInstanceService from '@/lib/api/evolution-instance'; // Ajuste o caminho se necessário
import * as inboxService from '@/lib/api/inbox'; // Ajuste o caminho se necessário
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
// NEW: Import Select components from shadcn/ui
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Loader2, Terminal, ArrowLeft, QrCode, CheckCircle, XCircle, WifiOff, Clock, RefreshCw, Users, Bot } from "lucide-react";
import { toast } from "sonner";
import { ConfigureEvolutionApiStep } from '@/components/ui/inbox/create/configure-evolution-api'; // Ajuste o caminho se necessário

// Local ConnectionStatus type for ConfigureEvolutionApiStep internal state reporting
type ConfigureStepStatus = 'IDLE' | 'CREATING_INSTANCE' | 'FETCHING_QR' | 'WAITING_SCAN' | 'CONNECTED' | 'ERROR' | 'TIMEOUT' | 'SOCKET_ERROR';

// NEW: Default status for new conversations
const DEFAULT_INITIAL_STATUS: ConversationStatusOption = 'BOT';

/**
 * Edit settings for an existing Inbox.
 * Allows modifying name, initial conversation behavior, and re-connecting channels.
 * @page
 */
export default function EditInboxPage() {
    const router = useRouter();
    const params = useParams();
    const authenticatedFetch = useAuthenticatedFetch();
    const { setPageTitle } = useLayoutContext();

    const inboxId = useMemo(() => {
        const id = params?.inboxId;
        return typeof id === 'string' ? id : null;
    }, [params?.inboxId]);

    // --- State Management ---
    const [inboxData, setInboxData] = useState<Inbox | null>(null); // Stores original fetched data
    const [name, setName] = useState<string>('');
    // const [enableAutoAssignment, setEnableAutoAssignment] = useState<boolean>(true); // Example if auto-assignment was used
    // NEW: State for the initial conversation status setting
    const [initialConversationStatus, setInitialConversationStatus] = useState<ConversationStatusOption>(DEFAULT_INITIAL_STATUS);
    const [isLoading, setIsLoading] = useState<boolean>(true); // For initial page load
    const [isSaving, setIsSaving] = useState<boolean>(false); // For saving general settings
    const [error, setError] = useState<string | null>(null); // For fetch/update errors
    const [isDirty, setIsDirty] = useState<boolean>(false); // Tracks form changes

    // --- State for Evolution Connection ---
    const [showQrCodeSection, setShowQrCodeSection] = useState<boolean>(false);
    const [currentDbStatus, setCurrentDbStatus] = useState<EvolutionInstanceStatus | null>(null);
    const [isSyncingStatus, setIsSyncingStatus] = useState<boolean>(false); // Loading state for sync button
    const [configureStepStatus, setConfigureStepStatus] = useState<ConfigureStepStatus>('IDLE');
    const [configureStepError, setConfigureStepError] = useState<string | null>(null);

    // --- Helper to get Evolution Instance ID ---
    const getEvolutionInstanceId = (): string | null => {
        if (inboxData?.channel_type === 'whatsapp_evolution_api') {
            if (inboxData.channel_details?.id) {
                return inboxData.channel_details.id;
            }
            if (inboxData.channel_id) {
                return inboxData.channel_id;
            }
        }
        return null;
    };
    const evolutionInstanceId = useMemo(getEvolutionInstanceId, [inboxData]);

    // --- Set Page Title ---
    useEffect(() => {
        setPageTitle(
            // UPDATE: Reverted user-facing text to pt-BR
            <div className="flex items-center gap-2">
                <Link href="/dashboard/inboxes" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground" aria-label="Voltar para Caixas de Entrada">
                    <ArrowLeft className="h-4 w-4" />
                    <span className="font-normal">Caixas de Entrada</span>
                </Link>
                <span className="text-sm text-muted-foreground">/</span>
                <span className="font-semibold text-md">
                    {isLoading ? 'Carregando Configurações...' : inboxData ? `Configurações: ${inboxData.name}` : 'Configurações da Caixa de Entrada'}
                </span>
            </div>
        );
    }, [setPageTitle, isLoading, inboxData]);

    // --- Fetch Initial Inbox Data ---
    const fetchAndSetInboxData = useCallback(async () => {
        if (!inboxId) {
            // UPDATE: Reverted user-facing text to pt-BR
            setError("ID da caixa de entrada não encontrado na URL.");
            setIsLoading(false);
            return;
        }
        setIsLoading(true);
        setError(null);
        try {
            const data = await inboxService.getInboxById(inboxId, authenticatedFetch);
            setInboxData(data);
            setName(data.name);
            setInitialConversationStatus(data.initial_conversation_status ?? DEFAULT_INITIAL_STATUS);
            setIsDirty(false);
            setCurrentDbStatus(data.connection_status as EvolutionInstanceStatus ?? 'UNKNOWN');
            setShowQrCodeSection(false);
            setIsSyncingStatus(false);
            setConfigureStepStatus('IDLE');
            setConfigureStepError(null);
        } catch (err: unknown) {
            // UPDATE: Reverted user-facing text to pt-BR
            const message = err instanceof Error ? err.message : "Falha ao carregar os detalhes da caixa de entrada.";
            setError(message);
            setInboxData(null);
            setCurrentDbStatus('UNKNOWN');
        } finally {
            setIsLoading(false);
        }
    }, [inboxId, authenticatedFetch]);

    useEffect(() => {
        fetchAndSetInboxData();
    }, [fetchAndSetInboxData]);

    // --- Monitor Form Changes (Dirty State) ---
    useEffect(() => {
        if (!inboxData) return;
        const nameChanged = name !== inboxData.name;
        const statusChanged = initialConversationStatus !== (inboxData.initial_conversation_status ?? DEFAULT_INITIAL_STATUS);
        setIsDirty(nameChanged || statusChanged);
    }, [name, initialConversationStatus, inboxData]);

    // --- Function to Save General Settings ---
    const handleSave = useCallback(async () => {
        if (!inboxId || !isDirty || isSaving || !inboxData) return;

        // UPDATE: Reverted user-facing text to pt-BR (in toasts)
        if (!name.trim()) {
            toast.error("O nome da caixa de entrada não pode estar vazio.");
            return;
        }
        if (name.trim().length > 100) {
            toast.error("O nome da caixa de entrada não pode exceder 100 caracteres.");
            return;
        }
        if (initialConversationStatus !== 'BOT' && initialConversationStatus !== 'PENDING') {
             toast.error("Status inicial da conversa inválido selecionado.");
            return;
        }

        setIsSaving(true);
        setError(null);
        // UPDATE: Reverted user-facing text to pt-BR
        const toastId = toast.loading("Salvando alterações...");

        const payload: InboxUpdatePayload = {};
        if (name.trim() !== inboxData.name) {
            payload.name = name.trim();
        }
        if (initialConversationStatus !== (inboxData.initial_conversation_status ?? DEFAULT_INITIAL_STATUS)) {
             payload.initial_conversation_status = initialConversationStatus;
        }

        if (Object.keys(payload).length === 0) {
             toast.dismiss(toastId);
             setIsSaving(false);
             setIsDirty(false);
             return;
        }

        try {
            const updatedInbox = await inboxService.updateInbox(inboxId, payload, authenticatedFetch);
            setInboxData(updatedInbox);
            setName(updatedInbox.name);
            setInitialConversationStatus(updatedInbox.initial_conversation_status ?? DEFAULT_INITIAL_STATUS);
            setCurrentDbStatus(updatedInbox.connection_status as EvolutionInstanceStatus ?? 'UNKNOWN');
            setIsDirty(false);
            // UPDATE: Reverted user-facing text to pt-BR
            toast.success("Caixa de entrada atualizada com sucesso!", { id: toastId });

        } catch (err: unknown) {
             // UPDATE: Reverted user-facing text to pt-BR
            const message = err instanceof Error ? err.message : "Falha ao salvar as alterações.";
            toast.error(`Falha na atualização: ${message}`, { id: toastId });
            setError(message);
        } finally {
            setIsSaving(false);
        }
    }, [inboxId, name, initialConversationStatus, inboxData, isDirty, isSaving, authenticatedFetch]);

    // --- Function to Cancel / Go Back ---
    const handleCancel = () => {
        router.push('/dashboard/inboxes');
    };

    // --- Function to Sync Connection Status ---
    const handleSyncStatus = useCallback(async () => {
        if (!evolutionInstanceId || isSyncingStatus) return;

        setIsSyncingStatus(true);
         // UPDATE: Reverted user-facing text to pt-BR
        const toastId = toast.loading("Sincronizando status da conexão...");

        try {
            const updatedInstance = await evolutionInstanceService.syncEvolutionInstanceStatus(
                evolutionInstanceId,
                authenticatedFetch
            );
            setCurrentDbStatus(updatedInstance.status);
            // UPDATE: Reverted user-facing text to pt-BR (uses status which might be English, consider mapping if needed)
            toast.success(`Status atualizado: ${updatedInstance.status}`, { id: toastId });

            setInboxData(prev => prev ? ({ ...prev, connection_status: updatedInstance.status, status_last_checked_at: updatedInstance.updated_at }) : null);

        } catch (err: unknown) {
             // UPDATE: Reverted user-facing text to pt-BR
            const message = err instanceof Error ? err.message : "Falha ao sincronizar o status.";
            toast.error(`Falha ao sincronizar: ${message}`, { id: toastId });
        } finally {
            setIsSyncingStatus(false);
        }
    }, [evolutionInstanceId, authenticatedFetch, isSyncingStatus]);

    // --- Callbacks for ConfigureEvolutionApiStep ---
    const handleEvolutionConnectionSuccess = useCallback(() => {
         // UPDATE: Reverted user-facing text to pt-BR
        toast.success("Conexão do WhatsApp estabelecida!");
        setCurrentDbStatus('CONNECTED');
    }, []);

    const handleEvolutionStatusChange = useCallback((status: ConfigureStepStatus, errorMsg?: string | null) => {
        setConfigureStepStatus(status);
        setConfigureStepError(errorMsg ?? null);
        if (status === 'CONNECTED') {
             setCurrentDbStatus('CONNECTED');
        } else if (status === 'ERROR' || status === 'TIMEOUT' || status === 'SOCKET_ERROR') {
             setCurrentDbStatus(prev => prev === 'CONNECTED' ? 'DISCONNECTED' : prev);
        }
    }, []);

    // --- Conditional Rendering ---

    if (isLoading) {
        // Skeleton structure remains the same
        return (
            <div className="px-4 py-6 md:px-6 lg:px-8 space-y-6">
                {/* General Settings Skeleton */}
                <Card className="w-full max-w-2xl mx-auto">
                    <CardHeader>
                        <Skeleton className="h-6 w-1/2 mb-2" />
                        <Skeleton className="h-4 w-3/4" />
                    </CardHeader>
                    <CardContent className="space-y-6">
                        <div className="space-y-2">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-10 w-full" />
                        </div>
                        {/* NEW: Add skeleton for Select */}
                         <div className="space-y-2">
                             <Skeleton className="h-4 w-32" />
                             <Skeleton className="h-10 w-full" />
                         </div>
                    </CardContent>
                    <CardFooter className="flex justify-end gap-2">
                        <Skeleton className="h-10 w-20" />
                        <Skeleton className="h-10 w-24" />
                    </CardFooter>
                </Card>
                {/* Connection Card Skeleton */}
                <Card className="w-full max-w-2xl mx-auto">
                     <CardHeader>
                        <Skeleton className="h-6 w-1/3 mb-2" />
                        <Skeleton className="h-4 w-full" />
                    </CardHeader>
                     <CardContent>
                         <Skeleton className="h-10 w-full" />
                    </CardContent>
                </Card>
            </div>
        );
    }

    if (error && !inboxData) {
        // UPDATE: Reverted user-facing text to pt-BR
        return (
            <div className="px-4 py-6 md:px-6 lg:px-8">
                <Alert variant="destructive">
                    <Terminal className="h-4 w-4" />
                    <AlertTitle>Erro ao Carregar a Caixa de Entrada</AlertTitle>
                    <AlertDescription>
                        {error}
                        <Button variant="link" size="sm" onClick={fetchAndSetInboxData} className="ml-2 p-0 h-auto">
                            Tentar novamente
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleCancel} className="ml-4">
                            Voltar para a Lista
                        </Button>
                    </AlertDescription>
                </Alert>
            </div>
        );
    }

    if (!inboxData) {
         // UPDATE: Reverted user-facing text to pt-BR
         return (
            <div className="px-4 py-6 md:px-6 lg:px-8">
                <Alert>
                    <Terminal className="h-4 w-4" />
                    <AlertTitle>Caixa de Entrada Não Encontrada</AlertTitle>
                    <AlertDescription>
                        A caixa de entrada solicitada não pôde ser encontrada ou você pode não ter permissão para visualizá-la.
                         <Button variant="outline" size="sm" onClick={handleCancel} className="ml-4">
                            Voltar para a Lista
                        </Button>
                    </AlertDescription>
                </Alert>
            </div>
        );
    }

    // --- Main Form Rendering ---
    return (
        <div className="px-4 pb-8 pt-2 md:px-6 md:pt-4 lg:px-8 space-y-6">
            {/* --- General Settings Card --- */}
            <Card className="w-full max-w-2xl mx-auto">
                 {/* UPDATE: Reverted user-facing text to pt-BR */}
                <CardHeader>
                    <CardTitle>Configurações da Caixa de Entrada</CardTitle>
                    <CardDescription>
                        Atualize o nome e as configurações da sua caixa de entrada '{inboxData.name}'.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Name Field */}
                     {/* UPDATE: Reverted user-facing text to pt-BR */}
                    <div className="space-y-2">
                        <Label htmlFor="inboxName">Nome da Caixa de Entrada *</Label>
                        <Input
                            id="inboxName"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Ex: WhatsApp da Equipe de Vendas"
                            required
                            maxLength={100}
                            disabled={isSaving}
                            aria-describedby="inboxNameHelp"
                        />
                        <p id="inboxNameHelp" className="text-sm text-muted-foreground">
                            Utilizado para identificar essa caixa de entrada na plataforma (máximo 100 caracteres).
                        </p>
                    </div>

                    {/* NEW: Initial Conversation Status Select */}
                     {/* UPDATE: Reverted user-facing text to pt-BR */}
                    <div className="space-y-2">
                        <Label htmlFor="initialStatus">Status Inicial da Conversa</Label>
                        <Select
                            value={initialConversationStatus}
                            onValueChange={(value: ConversationStatusOption) => setInitialConversationStatus(value)}
                            disabled={isSaving}
                        >
                            <SelectTrigger id="initialStatus" aria-describedby="initialStatusHelp">
                                <SelectValue placeholder="Selecione o status padrão..." />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="BOT">
                                    <div className="flex items-center gap-2">
                                        <Bot className="h-4 w-4" />
                                        <span>Começar com Robô</span>
                                    </div>
                                </SelectItem>
                                <SelectItem value="PENDING">
                                    <div className="flex items-center gap-2">
                                        <Users className="h-4 w-4" />
                                        <span>Começar Pendente (Requer Humano)</span>
                                    </div>
                                </SelectItem>
                            </SelectContent>
                        </Select>
                         <p id="initialStatusHelp" className="text-sm text-muted-foreground">
                            Escolha se novas conversas são inicialmente tratadas pelo robô ou colocadas na fila para um agente humano.
                         </p>
                    </div>

                    {/* Display general save errors */}
                     {/* UPDATE: Reverted user-facing text to pt-BR */}
                    {error && !isSaving && (
                        <Alert variant="destructive">
                            <Terminal className="h-4 w-4" />
                            <AlertTitle>Erro ao Salvar</AlertTitle>
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                </CardContent>
                 {/* UPDATE: Reverted user-facing text to pt-BR */}
                <CardFooter className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={handleCancel} disabled={isSaving}>
                        Cancelar
                    </Button>
                    <Button
                        type="button"
                        onClick={handleSave}
                        disabled={!isDirty || isSaving}
                    >
                        {isSaving ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Salvando...</> : 'Salvar Alterações'}
                    </Button>
                </CardFooter>
            </Card>

            {/* --- Evolution API Connection Section (Conditional) --- */}
            {inboxData.channel_type === 'whatsapp_evolution_api' && (
                 // UPDATE: Reverted user-facing text to pt-BR
                <Card className="w-full max-w-2xl mx-auto">
                    <CardHeader>
                        <CardTitle>Conexão do WhatsApp</CardTitle>
                        <CardDescription>
                            Gerencie o status da conexão para esta caixa de entrada da API Evolution.
                            {evolutionInstanceId && <span className="block text-xs text-muted-foreground mt-1">ID da Instância: {evolutionInstanceId}</span>}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Status Display and Actions */}
                         {/* UPDATE: Reverted user-facing text to pt-BR */}
                        <div className='flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 border rounded-md bg-muted/50'>
                             <div className='text-sm'>
                                {/* NOTE: EvolutionStatusDisplay component still returns English status text, but surrounding text is pt-BR */}
                                Status Atual: <EvolutionStatusDisplay status={currentDbStatus} />
                             </div>
                             <div className='flex gap-2 w-full sm:w-auto'>
                                 {/* Sync Button */}
                                 <Button
                                     variant="secondary"
                                     size="sm"
                                     onClick={handleSyncStatus}
                                     disabled={!evolutionInstanceId || isSyncingStatus || isSaving}
                                     className='flex-1 sm:flex-none'
                                     title="Verificar status da conexão com a API Evolution"
                                 >
                                     {isSyncingStatus ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                                     Sincronizar Status
                                 </Button>
                                 {/* Show/Hide QR Button */}
                                 <Button
                                     variant="outline"
                                     size="sm"
                                     onClick={() => setShowQrCodeSection(prev => !prev)}
                                     disabled={!evolutionInstanceId || isSaving}
                                     className='flex-1 sm:flex-none'
                                 >
                                     <QrCode className="mr-2 h-4 w-4" />
                                     {showQrCodeSection ? 'Ocultar QR' : 'Conectar / Reconectar'}
                                 </Button>
                             </div>
                        </div>

                        {/* Conditionally render the QR component */}
                        {showQrCodeSection && evolutionInstanceId && (
                            <div className='pt-4 border-t'>
                                <ConfigureEvolutionApiStep
                                    key={evolutionInstanceId}
                                    existingInstanceId={evolutionInstanceId}
                                    onConnectionSuccess={handleEvolutionConnectionSuccess}
                                    onStatusChange={handleEvolutionStatusChange}
                                />
                                {/* Display status/error from ConfigureStep while active */}
                                {/* UPDATE: Reverted user-facing text to pt-BR */}
                                {configureStepStatus !== 'IDLE' && configureStepStatus !== 'CONNECTED' && (
                                    <div className='mt-2 text-center text-sm text-muted-foreground'>
                                        {/* NOTE: EvolutionStatusDisplay still returns English status text */}
                                        Tentativa de Conexão: <EvolutionStatusDisplay status={configureStepStatus} error={configureStepError} />
                                    </div>
                                )}
                            </div>
                        )}
                        {/* Show alert if instance ID is missing */}
                        {/* UPDATE: Reverted user-facing text to pt-BR */}
                        {!evolutionInstanceId && (
                             <Alert variant="default">
                                <Terminal className="h-4 w-4" />
                                <AlertTitle>ID da Instância Ausente</AlertTitle>
                                <AlertDescription>
                                    Não é possível gerenciar a conexão porque o ID da Instância Evolution associado a esta caixa de entrada não pôde ser encontrado.
                                </AlertDescription>
                            </Alert>
                        )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}


// --- Helper Component for Status Display (Text remains English based on backend/enum values) ---
interface StatusDisplayProps {
    status: EvolutionInstanceStatus | ConfigureStepStatus | null;
    error?: string | null;
}

const EvolutionStatusDisplay: React.FC<StatusDisplayProps> = ({ status, error }) => {
    const errorTitle = error ? `Erro: ${error}` : '';

    switch (status) {
        case 'CONNECTED':
            // PT-BR: Conectado
            return <span className="inline-flex items-center gap-1 font-medium text-green-600"><CheckCircle className="h-4 w-4" /> Conectado</span>;
        case 'DISCONNECTED':
             // PT-BR: Desconectado
             return <span className="inline-flex items-center gap-1 font-medium text-red-600"><XCircle className="h-4 w-4" /> Desconectado</span>;
        case 'QRCODE':
        case 'WAITING_SCAN':
             // PT-BR: Precisa Escanear (Código QR)
            return <span className="inline-flex items-center gap-1 font-medium text-blue-600"><QrCode className="h-4 w-4" /> Precisa Escanear (Código QR)</span>;
        case 'FETCHING_QR':
             // PT-BR: Carregando QR
             return <span className="inline-flex items-center gap-1 font-medium text-blue-600"><Loader2 className="h-4 w-4 animate-spin" /> Carregando QR</span>;
        case 'TIMEOUT':
             // PT-BR: Tempo Esgotado
            return <span className="inline-flex items-center gap-1 font-medium text-orange-600"><Clock className="h-4 w-4" /> Tempo Esgotado</span>;
        case 'SOCKET_ERROR':
             // PT-BR: Erro de Socket
             return <span className="inline-flex items-center gap-1 font-medium text-red-600" title="Erro na conexão WebSocket"><WifiOff className="h-4 w-4" /> Erro de Socket</span>;
        case 'API_ERROR':
             // PT-BR: Erro na API
             return <span className="inline-flex items-center gap-1 font-medium text-red-600" title={errorTitle}><Terminal className="h-4 w-4" /> Erro na API</span>;
         case 'CONFIG_ERROR':
             // PT-BR: Erro de Configuração
             return <span className="inline-flex items-center gap-1 font-medium text-yellow-600" title="Verifique a URL/API Key"><Terminal className="h-4 w-4" /> Erro de Configuração</span>;
        case 'ERROR':
             // PT-BR: Erro
             return <span className="inline-flex items-center gap-1 font-medium text-red-600" title={errorTitle}><XCircle className="h-4 w-4" /> Erro</span>;
        case 'UNKNOWN':
        case 'IDLE':
        case 'CREATING_INSTANCE':
        default:
             // PT-BR: Desconhecido
            return <span className="inline-flex items-center gap-1 font-medium text-muted-foreground">Desconhecido</span>;
    }
};