'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch'; // Ajuste o caminho se necessário
import { useLayoutContext } from '@/contexts/layout-context'; // Ajuste o caminho se necessário
import { Inbox, InboxUpdatePayload } from '@/types/inbox'; // Ajuste o caminho se necessário
import { EvolutionInstance, EvolutionInstanceStatus } from '@/types/evolution-instance'; // Ajuste o caminho se necessário
import * as evolutionInstanceService from '@/lib/api/evolution-instance'; // Ajuste o caminho se necessário
import * as inboxService from '@/lib/api/inbox'; // Ajuste o caminho se necessário
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Loader2, Terminal, ArrowLeft, QrCode, CheckCircle, XCircle, WifiOff, Clock, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { ConfigureEvolutionApiStep } from '@/components/ui/inbox/create/configure-evolution-api'; // Ajuste o caminho se necessário

// Local ConnectionStatus type for ConfigureEvolutionApiStep internal state reporting
type ConfigureStepStatus = 'IDLE' | 'CREATING_INSTANCE' | 'FETCHING_QR' | 'WAITING_SCAN' | 'CONNECTED' | 'ERROR' | 'TIMEOUT' | 'SOCKET_ERROR';

/**
 * Componente de página para editar as configurações de uma Caixa de Entrada existente.
 * Permite a modificação do nome, atribuição automática e reconexão para canais da API Evolution.
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

    // --- Gerenciamento de Estado ---
    const [inboxData, setInboxData] = useState<Inbox | null>(null); // Armazena os dados buscados originalmente
    const [name, setName] = useState<string>('');
    const [enableAutoAssignment, setEnableAutoAssignment] = useState<boolean>(true);
    const [isLoading, setIsLoading] = useState<boolean>(true); // Para o carregamento inicial da página
    const [isSaving, setIsSaving] = useState<boolean>(false); // Para salvar as configurações gerais
    const [error, setError] = useState<string | null>(null); // Para erros de busca/atualização
    const [isDirty, setIsDirty] = useState<boolean>(false); // Acompanha se houve alterações no formulário

    // --- Estado para Conexão Evolution ---
    const [showQrCodeSection, setShowQrCodeSection] = useState<boolean>(false);
    // Armazena o status *dos dados da caixa* inicialmente
    const [currentDbStatus, setCurrentDbStatus] = useState<EvolutionInstanceStatus | null>(null);
    const [isSyncingStatus, setIsSyncingStatus] = useState<boolean>(false); // Estado de carregamento para o botão de sincronização
    // Estado para o status interno do ConfigureEvolutionApiStep (para exibição enquanto o QR é exibido)
    const [configureStepStatus, setConfigureStepStatus] = useState<ConfigureStepStatus>('IDLE');
    const [configureStepError, setConfigureStepError] = useState<string | null>(null);

    // --- Helper para obter o ID da Instância Evolution ---
    // Acessa com segurança o ID aninhado, assumindo que está armazenado sob 'id' em channel_details
    // Ou utiliza channel_id como alternativa, se presente
    const getEvolutionInstanceId = (): string | null => {
        if (inboxData?.channel_type === 'whatsapp_evolution_api') {
            if (inboxData.channel_details && typeof inboxData.channel_details === 'object') {
                // *** Ajuste a chave 'id' se o backend usar outro nome em channel_details ***
                const detailsId = (inboxData.channel_details as any).id;
                if (detailsId) return detailsId;
            }
            // Alternativa para channel_id se details não tiver 'id' ou estiver ausente
            if (inboxData.channel_id) {
                return inboxData.channel_id;
            }
        }
        return null;
    };
    const evolutionInstanceId = useMemo(getEvolutionInstanceId, [inboxData]);

    // --- Definir Título da Página ---
    useEffect(() => {
        setPageTitle(
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

    // --- Buscar Dados Iniciais da Caixa de Entrada ---
    const fetchAndSetInboxData = useCallback(async () => {
        if (!inboxId) {
            setError("ID da caixa de entrada não encontrado na URL.");
            setIsLoading(false);
            return;
        }
        setIsLoading(true);
        setError(null);
        console.log(`[EditInboxPage] Buscando dados da caixa para ID: ${inboxId}`);
        try {
            const data = await inboxService.getInboxById(inboxId, authenticatedFetch);
            setInboxData(data);
            // Inicializa o estado do formulário com os dados buscados
            setName(data.name);
            setEnableAutoAssignment(data.enable_auto_assignment ?? true); // Padrão para verdadeiro se null/undefined
            setIsDirty(false); // Reseta o estado de alterações após a busca
            // Define o status inicial com base nos dados buscados
            setCurrentDbStatus(data.connection_status as EvolutionInstanceStatus ?? 'UNKNOWN');
            // Reseta outros estados
            setShowQrCodeSection(false);
            setIsSyncingStatus(false);
            setConfigureStepStatus('IDLE');
            setConfigureStepError(null);
            console.log("[EditInboxPage] Dados da caixa buscados:", data);
        } catch (err: unknown) {
            console.error("[EditInboxPage] Erro na busca:", err);
            const message = err instanceof Error ? err.message : "Falha ao carregar os detalhes da caixa de entrada.";
            setError(message);
            setInboxData(null); // Limpa os dados em caso de erro
            setCurrentDbStatus('UNKNOWN'); // Define como desconhecido em caso de erro na busca
        } finally {
            setIsLoading(false);
        }
    }, [inboxId, authenticatedFetch]);

    useEffect(() => {
        fetchAndSetInboxData();
    }, [fetchAndSetInboxData]); // Executa a busca ao montar o componente e se a função de busca mudar

    // --- Monitorar Alterações do Formulário (Estado Dirty) ---
    useEffect(() => {
        if (!inboxData) return; // Não compara se os dados originais não foram carregados

        const nameChanged = name !== inboxData.name;
        const autoAssignChanged = enableAutoAssignment !== (inboxData.enable_auto_assignment ?? true);

        setIsDirty(nameChanged || autoAssignChanged);

    }, [name, enableAutoAssignment, inboxData]);

    // --- Função para Salvar Configurações Gerais ---
    const handleSave = useCallback(async () => {
        if (!inboxId || !isDirty || isSaving || !inboxData) return;

        // Validação básica
        if (!name.trim()) {
            toast.error("O nome da caixa de entrada não pode estar vazio.");
            return;
        }
        if (name.trim().length > 100) {
            toast.error("O nome da caixa de entrada não pode exceder 100 caracteres.");
            return;
        }

        setIsSaving(true);
        setError(null); // Limpa erros anteriores na nova tentativa de salvar
        const toastId = toast.loading("Salvando alterações...");

        // Constrói o payload apenas com os campos que foram alterados
        const payload: InboxUpdatePayload = {};
        if (name !== inboxData.name) {
            payload.name = name.trim();
        }
        if (enableAutoAssignment !== (inboxData.enable_auto_assignment ?? true)) {
            payload.enable_auto_assignment = enableAutoAssignment;
        }

        // Se nenhum campo foi alterado (por exemplo, apenas remoção de espaços), não chama a API
        if (Object.keys(payload).length === 0) {
             toast.dismiss(toastId);
             setIsSaving(false);
             setIsDirty(false); // Reseta o estado dirty, pois efetivamente nenhuma alteração foi salva
             return;
        }

        try {
            console.log("[EditInboxPage] Atualizando caixa com payload:", payload);
            const updatedInbox = await inboxService.updateInbox(inboxId, payload, authenticatedFetch);

            // IMPORTANTE: Atualiza o estado local com a resposta do servidor
            setInboxData(updatedInbox); // Atualiza os dados base
            setName(updatedInbox.name); // Sincroniza o estado do formulário
            setEnableAutoAssignment(updatedInbox.enable_auto_assignment ?? true);
            // Atualiza o status a partir dos dados potencialmente atualizados também
            setCurrentDbStatus(updatedInbox.connection_status as EvolutionInstanceStatus ?? 'UNKNOWN');
            setIsDirty(false); // Reseta o estado dirty após a atualização bem-sucedida

            toast.success("Caixa de entrada atualizada com sucesso!", { id: toastId });
            console.log("[EditInboxPage] Caixa atualizada:", updatedInbox);

        } catch (err: unknown) {
            console.error("[EditInboxPage] Erro na atualização:", err);
            const message = err instanceof Error ? err.message : "Falha ao salvar as alterações.";
            toast.error(`Falha na atualização: ${message}`, { id: toastId });
            setError(message); // Exibe o erro no alerta também
        } finally {
            setIsSaving(false);
        }
    }, [inboxId, name, enableAutoAssignment, inboxData, isDirty, isSaving, authenticatedFetch]);

    // --- Função para Cancelar / Voltar ---
    const handleCancel = () => {
        router.push('/dashboard/inboxes'); // Navega de volta para a lista
    };

    // --- Função para Sincronizar o Status ---
    const handleSyncStatus = useCallback(async () => {
        if (!evolutionInstanceId || isSyncingStatus) return;

        setIsSyncingStatus(true);
        const toastId = toast.loading("Sincronizando status da conexão...");

        try {
            // Chama a nova função de serviço usando o *ID da Instância Evolution*
            const updatedInstance = await evolutionInstanceService.syncEvolutionInstanceStatus(
                evolutionInstanceId,
                authenticatedFetch
            );
            // Atualiza o status exibido com base na resposta
            setCurrentDbStatus(updatedInstance.status);
            toast.success(`Status atualizado: ${updatedInstance.status}`, { id: toastId });

            // Também atualiza levemente o estado principal da caixa para refletir o possível novo 'updated_at' da instância
            setInboxData(prev => prev ? ({ ...prev, connection_status: updatedInstance.status, status_last_checked_at: updatedInstance.updated_at }) : null);

        } catch (err: unknown) {
            console.error("Erro ao sincronizar status:", err);
            const message = err instanceof Error ? err.message : "Falha ao sincronizar o status.";
            toast.error(`Falha ao sincronizar: ${message}`, { id: toastId });
            // Opcional: definir o status para API_ERROR em caso de falha
            // setCurrentDbStatus('API_ERROR');
        } finally {
            setIsSyncingStatus(false);
        }
    }, [evolutionInstanceId, authenticatedFetch, isSyncingStatus]);

    // --- Callbacks para ConfigureEvolutionApiStep ---
    const handleEvolutionConnectionSuccess = useCallback(() => {
        toast.success("Conexão do WhatsApp estabelecida!");
        // Atualiza a exibição principal do status após a conexão bem-sucedida via QR
        setCurrentDbStatus('CONNECTED');
        // Opcional: ocultar a seção de QR após o sucesso
        // setShowQrCodeSection(false);
    }, []);

    const handleEvolutionStatusChange = useCallback((status: ConfigureStepStatus, errorMsg?: string | null) => {
        // Atualiza o status *enquanto o componente de QR estiver ativo*
        console.log("[EditInboxPage] Atualização de status do ConfigureStep:", status, errorMsg);
        setConfigureStepStatus(status);
        setConfigureStepError(errorMsg ?? null);
        // Se o componente reportar conectado, também atualiza a exibição principal do status
        if (status === 'CONNECTED') {
             setCurrentDbStatus('CONNECTED');
        } else if (status === 'ERROR' || status === 'TIMEOUT' || status === 'SOCKET_ERROR') {
            // Se a tentativa de escanear o QR falhar, reflete que o status no banco pode estar desatualizado até a próxima sincronização
             setCurrentDbStatus(prev => prev === 'CONNECTED' ? 'DISCONNECTED' : prev); // Exemplo: assume desconectado se a conexão falhar
        }
    }, []);

    // --- Renderização Condicional ---

    if (isLoading) {
        return (
            <div className="px-4 py-6 md:px-6 lg:px-8 space-y-6">
                {/* Esqueleto das Configurações Gerais */}
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
                        <div className="flex items-center space-x-2">
                            <Skeleton className="h-6 w-10 rounded-full" />
                            <Skeleton className="h-4 w-32" />
                        </div>
                    </CardContent>
                    <CardFooter className="flex justify-end gap-2">
                        <Skeleton className="h-10 w-20" />
                        <Skeleton className="h-10 w-24" />
                    </CardFooter>
                </Card>
                {/* Esqueleto do Cartão de Conexão */}
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

    if (error && !inboxData) { // Mostra erro crítico somente se os dados não puderam ser carregados
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

    if (!inboxData) { // Trata o caso em que o carregamento terminou, mas os dados continuam nulos (por exemplo, caixa não encontrada)
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

    // --- Renderização Principal do Formulário ---
    return (
        <div className="px-4 pb-8 pt-2 md:px-6 md:pt-4 lg:px-8 space-y-6"> {/* Adicionado espaço vertical */}
            {/* --- Cartão de Configurações Gerais --- */}
            <Card className="w-full max-w-2xl mx-auto">
                <CardHeader>
                    <CardTitle>Configurações da Caixa de Entrada</CardTitle>
                    <CardDescription>
                        Atualize o nome e as configurações da sua caixa de entrada '{inboxData.name}'.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Campo de Nome */}
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

                    {/* Comutador de Atribuição Automática */}
                    {/* <div className="flex items-center justify-between rounded-lg border p-4">
                         <div className="space-y-0.5">
                            <Label htmlFor="autoAssign" className="text-base">
                                Habilitar Atribuição Automática
                            </Label>
                            <p className="text-sm text-muted-foreground">
                                Atribui automaticamente novas conversas nesta caixa de entrada aos agentes disponíveis.
                            </p>
                        </div>
                        <Switch
                            id="autoAssign"
                            checked={enableAutoAssignment}
                            onCheckedChange={setEnableAutoAssignment}
                            disabled={isSaving}
                            aria-label="Alternar atribuição automática de conversas"
                        />
                    </div> */}

                    {/* Exibir erros gerais de salvamento */}
                    {error && !isSaving && (
                        <Alert variant="destructive">
                            <Terminal className="h-4 w-4" />
                            <AlertTitle>Erro ao Salvar</AlertTitle>
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                </CardContent>
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

            {/* --- Seção de Conexão da API Evolution (Condicional) --- */}
            {inboxData.channel_type === 'whatsapp_evolution_api' && (
                <Card className="w-full max-w-2xl mx-auto">
                    <CardHeader>
                        <CardTitle>Conexão do WhatsApp</CardTitle>
                        <CardDescription>
                            Gerencie o status da conexão para esta caixa de entrada da API Evolution.
                            {evolutionInstanceId && <span className="block text-xs text-muted-foreground mt-1">ID da Instância: {evolutionInstanceId}</span>}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Exibição do Status e Ações */}
                        <div className='flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 border rounded-md bg-muted/50'>
                             <div className='text-sm'>
                                Status Atual: <EvolutionStatusDisplay status={currentDbStatus} />
                             </div>
                             <div className='flex gap-2 w-full sm:w-auto'>
                                 {/* Botão de Sincronização */}
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
                                 {/* Botão para Exibir/Ocultar QR */}
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

                        {/* Renderiza condicionalmente o componente de QR */}
                        {showQrCodeSection && evolutionInstanceId && (
                            <div className='pt-4 border-t'>
                                <ConfigureEvolutionApiStep
                                    key={evolutionInstanceId}
                                    existingInstanceId={evolutionInstanceId}
                                    onConnectionSuccess={handleEvolutionConnectionSuccess}
                                    onStatusChange={handleEvolutionStatusChange}
                                />
                                {/* Exibe o status/erro do próprio ConfigureStep enquanto estiver ativo */}
                                {configureStepStatus !== 'IDLE' && configureStepStatus !== 'CONNECTED' && (
                                    <div className='mt-2 text-center text-sm text-muted-foreground'>
                                        Tentativa de Conexão: <EvolutionStatusDisplay status={configureStepStatus} error={configureStepError} />
                                    </div>
                                )}
                            </div>
                        )}
                        {/* Exibe alerta se o ID da instância estiver ausente */}
                        {!evolutionInstanceId && (
                             <Alert variant="warning">
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


// --- Componente Auxiliar para Exibição de Status (utilizando EvolutionInstanceStatus) ---
interface StatusDisplayProps {
    status: EvolutionInstanceStatus | ConfigureStepStatus | null; // Aceita ambos os tipos
    error?: string | null;
}

const EvolutionStatusDisplay: React.FC<StatusDisplayProps> = ({ status, error }) => {
    const errorTitle = error ? `Erro: ${error}` : '';

    switch (status) {
        case 'CONNECTED':
            return <span className="inline-flex items-center gap-1 font-medium text-green-600"><CheckCircle className="h-4 w-4" /> Conectado</span>;
        case 'DISCONNECTED':
             return <span className="inline-flex items-center gap-1 font-medium text-red-600"><XCircle className="h-4 w-4" /> Desconectado</span>;
        case 'QRCODE':
        case 'WAITING_SCAN': 
            return <span className="inline-flex items-center gap-1 font-medium text-blue-600"><QrCode className="h-4 w-4" /> Precisa Escanear (Código QR)</span>;
        case 'FETCHING_QR':
             return <span className="inline-flex items-center gap-1 font-medium text-blue-600"><Loader2 className="h-4 w-4 animate-spin" /> Carregando QR</span>;
        case 'TIMEOUT':
            return <span className="inline-flex items-center gap-1 font-medium text-orange-600"><Clock className="h-4 w-4" /> Tempo Esgotado</span>;
        case 'SOCKET_ERROR':
             return <span className="inline-flex items-center gap-1 font-medium text-red-600" title="Erro na conexão WebSocket"><WifiOff className="h-4 w-4" /> Erro de Socket</span>;
        case 'API_ERROR':
             return <span className="inline-flex items-center gap-1 font-medium text-red-600" title={errorTitle}><Terminal className="h-4 w-4" /> Erro na API</span>;
         case 'CONFIG_ERROR':
             return <span className="inline-flex items-center gap-1 font-medium text-yellow-600" title="Verifique a URL/API Key"><Terminal className="h-4 w-4" /> Erro de Configuração</span>;
        case 'ERROR':
             return <span className="inline-flex items-center gap-1 font-medium text-red-600" title={errorTitle}><XCircle className="h-4 w-4" /> Erro</span>;
        case 'UNKNOWN':
        case 'IDLE':
        case 'CREATING_INSTANCE':
        default:
            return <span className="inline-flex items-center gap-1 font-medium text-muted-foreground">Desconhecido</span>;
    }
};
