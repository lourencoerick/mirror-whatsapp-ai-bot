"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import * as evolutionInstanceService from "@/lib/api/evolution-instance";
import * as inboxService from "@/lib/api/inbox";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";

// Tipos importados do OpenAPI via @/types/api
import { components } from "@/types/api";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { ConfigureEvolutionApiStep } from "@/components/ui/inbox/create/configure-evolution-api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  ArrowLeft,
  Bot,
  CheckCircle,
  Clock,
  Info,
  Loader2,
  QrCode,
  RefreshCw,
  Terminal,
  Users,
  WifiOff,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

// Tipos do backend/OpenAPI
type Inbox = components["schemas"]["InboxRead"];
type InboxUpdatePayload = components["schemas"]["InboxUpdate"];
type ConversationStatusOption = components["schemas"]["ConversationStatusEnum"];
type EvolutionInstanceStatus = components["schemas"]["EvolutionInstanceStatus"];

// Local ConnectionStatus type for ConfigureEvolutionApiStep internal state reporting
type ConfigureStepStatus =
  | "IDLE"
  | "QRCODE"
  | "CONFIG_ERROR"
  | "CREATING_INSTANCE"
  | "FETCHING_QR"
  | "WAITING_SCAN"
  | "CONNECTED"
  | "ERROR"
  | "TIMEOUT"
  | "SOCKET_ERROR";

const DEFAULT_INITIAL_STATUS: ConversationStatusOption = "PENDING"; // Ou "BOT" se preferir

export default function EditInboxPage() {
  const router = useRouter();
  const params = useParams();
  const authenticatedFetch = useAuthenticatedFetch();
  const { setPageTitle } = useLayoutContext();

  const inboxId = useMemo(() => {
    const id = params?.inboxId;
    return typeof id === "string" ? id : null;
  }, [params?.inboxId]);

  const [inboxData, setInboxData] = useState<Inbox | null>(null);
  const [name, setName] = useState<string>("");
  const [initialConversationStatus, setInitialConversationStatus] =
    useState<ConversationStatusOption>(DEFAULT_INITIAL_STATUS);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState<boolean>(false);

  const [showQrCodeSection, setShowQrCodeSection] = useState<boolean>(false);
  const [currentDbStatus, setCurrentDbStatus] =
    useState<EvolutionInstanceStatus | null>(null);
  const [isSyncingStatus, setIsSyncingStatus] = useState<boolean>(false);
  const [configureStepStatus, setConfigureStepStatus] =
    useState<ConfigureStepStatus>("IDLE");
  const [configureStepError, setConfigureStepError] = useState<string | null>(
    null
  );

  // Corrigido: Obter o ID da instância Evolution do objeto aninhado
  const evolutionInstanceIdForConfigStep = useMemo(() => {
    if (inboxData?.channel_type === "whatsapp_evolution") {
      return inboxData.evolution_instance?.id || null;
    }
    return null;
  }, [inboxData]);

  useEffect(() => {
    setPageTitle(
      <div className="flex items-center gap-2">
        <Link
          href="/dashboard/inboxes"
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          aria-label="Voltar para Caixas de Entrada"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="font-normal">Caixas de Entrada</span>
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        {isLoading ? (
          <span className="font-semibold text-md">
            Carregando Configurações...
          </span>
        ) : inboxData ? (
          `Configurações: ${inboxData.name}`
        ) : (
          `Configurações da Caixa de Entrada`
        )}
      </div>
    );
  }, [setPageTitle, isLoading, inboxData]);

  const fetchAndSetInboxData = useCallback(async () => {
    if (!inboxId) {
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
      setInitialConversationStatus(
        data.initial_conversation_status ?? DEFAULT_INITIAL_STATUS
      );
      setIsDirty(false);

      if (
        data.channel_type === "whatsapp_evolution" &&
        data.evolution_instance
      ) {
        setCurrentDbStatus(data.evolution_instance.status);
      } else {
        setCurrentDbStatus(null); // Nenhum status de DB para outros tipos ou se não houver instância
      }
      setShowQrCodeSection(false);
      setIsSyncingStatus(false);
      setConfigureStepStatus("IDLE");
      setConfigureStepError(null);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Falha ao carregar os detalhes da caixa de entrada.";
      setError(message);
      setInboxData(null);
      setCurrentDbStatus(null);
    } finally {
      setIsLoading(false);
    }
  }, [inboxId, authenticatedFetch]);

  useEffect(() => {
    fetchAndSetInboxData();
  }, [fetchAndSetInboxData]);

  useEffect(() => {
    if (!inboxData) return;
    const nameChanged = name !== inboxData.name;
    const statusChanged =
      initialConversationStatus !==
      (inboxData.initial_conversation_status ?? DEFAULT_INITIAL_STATUS);
    setIsDirty(nameChanged || statusChanged);
  }, [name, initialConversationStatus, inboxData]);

  const handleSave = useCallback(async () => {
    if (!inboxId || !isDirty || isSaving || !inboxData) return;
    if (!name.trim()) {
      toast.error("O nome da caixa de entrada não pode estar vazio.");
      return;
    }
    // ... (outras validações se necessário)

    setIsSaving(true);
    setError(null);
    const toastId = toast.loading("Salvando alterações...");

    const payload: InboxUpdatePayload = {};
    if (name.trim() !== inboxData.name) payload.name = name.trim();
    if (
      initialConversationStatus !==
      (inboxData.initial_conversation_status ?? DEFAULT_INITIAL_STATUS)
    ) {
      payload.initial_conversation_status = initialConversationStatus;
    }

    if (Object.keys(payload).length === 0) {
      toast.dismiss(toastId);
      setIsSaving(false);
      setIsDirty(false);
      return;
    }

    try {
      const updatedInbox = await inboxService.updateInbox(
        inboxId,
        payload,
        authenticatedFetch
      );
      setInboxData(updatedInbox); // Atualiza inboxData com a resposta completa
      setName(updatedInbox.name);
      setInitialConversationStatus(
        updatedInbox.initial_conversation_status ?? DEFAULT_INITIAL_STATUS
      );

      if (
        updatedInbox.channel_type === "whatsapp_evolution" &&
        updatedInbox.evolution_instance
      ) {
        setCurrentDbStatus(updatedInbox.evolution_instance.status);
      }
      setIsDirty(false);
      toast.success("Caixa de entrada atualizada com sucesso!", {
        id: toastId,
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Falha ao salvar as alterações.";
      toast.error(`Falha na atualização: ${message}`, { id: toastId });
      setError(message); // Pode ser útil exibir o erro no formulário também
    } finally {
      setIsSaving(false);
    }
  }, [
    inboxId,
    name,
    initialConversationStatus,
    inboxData,
    isDirty,
    isSaving,
    authenticatedFetch,
  ]);

  const handleCancel = () => router.push("/dashboard/inboxes");

  const handleSyncStatus = useCallback(async () => {
    // Usa evolutionInstanceIdForConfigStep que vem de inboxData.evolution_instance.id
    if (!evolutionInstanceIdForConfigStep || isSyncingStatus) return;
    setIsSyncingStatus(true);
    const toastId = toast.loading("Sincronizando status da conexão...");
    try {
      const updatedInstance =
        await evolutionInstanceService.syncEvolutionInstanceStatus(
          evolutionInstanceIdForConfigStep,
          authenticatedFetch
        );
      setCurrentDbStatus(updatedInstance.status);
      toast.success(`Status atualizado: ${updatedInstance.status}`, {
        id: toastId,
      });
      setInboxData((prev) => {
        if (!prev || !prev.evolution_instance) return prev;
        return {
          ...prev,
          evolution_instance: {
            ...prev.evolution_instance,
            status: updatedInstance.status,
            updated_at: updatedInstance.updated_at,
          },
        };
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Falha ao sincronizar o status.";
      toast.error(`Falha ao sincronizar: ${message}`, { id: toastId });
    } finally {
      setIsSyncingStatus(false);
    }
  }, [evolutionInstanceIdForConfigStep, authenticatedFetch, isSyncingStatus]);

  const handleEvolutionConnectionSuccess = useCallback(() => {
    toast.success("Conexão do WhatsApp estabelecida!");
    setCurrentDbStatus("CONNECTED"); // Assumindo que "CONNECTED" é um valor válido de EvolutionInstanceStatus
    // Forçar um re-fetch dos dados da inbox para obter o status mais recente da instância no objeto inboxData.evolution_instance
    fetchAndSetInboxData();
  }, [fetchAndSetInboxData]);

  const handleEvolutionStatusChange = useCallback(
    (status: ConfigureStepStatus, errorMsg?: string | null) => {
      setConfigureStepStatus(status);
      setConfigureStepError(errorMsg ?? null);
      if (status === "CONNECTED") {
        setCurrentDbStatus("CONNECTED");
      } else if (
        status === "ERROR" ||
        status === "TIMEOUT" ||
        status === "SOCKET_ERROR"
      ) {
        // Não mudar currentDbStatus aqui, ele reflete o status do DB.
        // O status do passo de configuração é temporário.
      }
    },
    []
  );

  // Construir a URL do Webhook para WhatsApp Cloud
  const webhookBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const whatsAppCloudWebhookUrl = useMemo(() => {
    if (
      inboxData?.channel_type === "whatsapp_cloud" &&
      inboxData.whatsapp_cloud_config?.phone_number_id
    ) {
      return `${webhookBaseUrl}/webhooks/whatsapp/cloud/${inboxData.whatsapp_cloud_config.phone_number_id}`;
    }
    return null;
  }, [inboxData, webhookBaseUrl]);

  if (isLoading) {
    /* ... Skeleton ... */
  }
  if (error && !inboxData) {
    /* ... Error ao Carregar ... */
  }
  if (!inboxData) {
    /* ... Caixa de Entrada Não Encontrada ... */
  }

  return (
    <div className="px-4 pb-8 pt-2 md:px-6 md:pt-4 lg:px-8 space-y-6">
      <Card className="w-full max-w-2xl mx-auto">
        <CardHeader>
          <CardTitle>Configurações da Caixa de Entrada</CardTitle>
          <CardDescription>
            Atualize o nome e as configurações da sua caixa de entrada &apos;
            {inboxData?.name}&apos;.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
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
              Utilizado para identificar essa caixa de entrada na plataforma
              (máximo 100 caracteres).
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="initialStatus">Status Inicial da Conversa</Label>
            <Select
              value={initialConversationStatus}
              onValueChange={(value: ConversationStatusOption) =>
                setInitialConversationStatus(value)
              }
              disabled={isSaving}
            >
              <SelectTrigger
                id="initialStatus"
                aria-describedby="initialStatusHelp"
              >
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
              Escolha se novas conversas são inicialmente tratadas pelo robô ou
              colocadas na fila para um agente humano.
            </p>
          </div>
          {error && !isSaving && (
            <Alert variant="destructive">
              <Terminal className="h-4 w-4" />
              <AlertTitle>Erro ao Salvar</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
        <CardFooter className="flex justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={isSaving}
          >
            Cancelar
          </Button>
          <Button
            type="button"
            onClick={handleSave}
            disabled={!isDirty || isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Salvando...
              </>
            ) : (
              "Salvar Alterações"
            )}
          </Button>
        </CardFooter>
      </Card>

      {/* Seção de Configuração do Canal WhatsApp Cloud */}
      {inboxData?.channel_type === "whatsapp_cloud" &&
        inboxData?.whatsapp_cloud_config && (
          <Card className="w-full max-w-2xl mx-auto">
            <CardHeader>
              <CardTitle>Configuração do Canal: WhatsApp Cloud API</CardTitle>
              <CardDescription>
                Detalhes da sua conexão com a API Cloud do WhatsApp. Estes dados
                são apenas para visualização. Para alterar, pode ser necessário
                recriar a caixa de entrada.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label className="text-sm font-medium">
                  ID do Número de Telefone
                </Label>
                <p className="text-sm text-muted-foreground bg-muted p-2 rounded-md break-all">
                  {inboxData?.whatsapp_cloud_config.phone_number_id}
                </p>
              </div>
              <div className="space-y-1">
                <Label className="text-sm font-medium">
                  WABA ID (ID da Conta Empresarial)
                </Label>
                <p className="text-sm text-muted-foreground bg-muted p-2 rounded-md break-all">
                  {inboxData?.whatsapp_cloud_config.waba_id}
                </p>
              </div>
              {inboxData?.whatsapp_cloud_config.app_id && (
                <div className="space-y-1">
                  <Label className="text-sm font-medium">
                    App ID (ID do Aplicativo Meta)
                  </Label>
                  <p className="text-sm text-muted-foreground bg-muted p-2 rounded-md break-all">
                    {inboxData?.whatsapp_cloud_config.app_id}
                  </p>
                </div>
              )}
              <div className="space-y-1">
                <Label className="text-sm font-medium">
                  Token de Verificação do Webhook
                </Label>
                <div className="flex items-center gap-2">
                  <p className="text-sm text-muted-foreground bg-muted p-2 rounded-md break-all flex-grow">
                    {inboxData?.whatsapp_cloud_config.webhook_verify_token}
                  </p>
                  <CopyButton
                    valueToCopy={
                      inboxData?.whatsapp_cloud_config.webhook_verify_token
                    }
                  />
                </div>
              </div>
              {whatsAppCloudWebhookUrl && (
                <Alert>
                  <Info className="h-4 w-4" />
                  <AlertTitle className="text-sm">URL do Webhook</AlertTitle>
                  <AlertDescription className="text-xs space-y-1">
                    <p>
                      Configure esta URL no seu App Meta (WhatsApp {">"}{" "}
                      Configuração):
                    </p>
                    <div className="flex items-center gap-2">
                      <code className="block break-all rounded bg-background px-2 py-1 font-mono text-xs border flex-grow">
                        {whatsAppCloudWebhookUrl}
                      </code>
                      <CopyButton valueToCopy={whatsAppCloudWebhookUrl} />
                    </div>
                    <p>
                      Use o Token de Verificação exibido acima. Assine os
                      eventos de `messages`.
                    </p>
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        )}

      {/* Seção de Conexão da Evolution API */}
      {inboxData?.channel_type === "whatsapp_evolution" && (
        <Card className="w-full max-w-2xl mx-auto">
          <CardHeader>
            <CardTitle>Conexão do WhatsApp (Evolution API)</CardTitle>
            <CardDescription>
              Gerencie o status da conexão para esta caixa de entrada da API
              Evolution.
              {inboxData.evolution_instance?.id && ( // Usar o ID da instância carregada
                <span className="block text-xs text-muted-foreground mt-1">
                  ID da Instância: {inboxData.evolution_instance.id}
                </span>
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3 border rounded-md bg-muted/50">
              <div className="text-sm">
                Status Atual:{" "}
                <EvolutionStatusDisplay status={currentDbStatus} />
              </div>
              <div className="flex gap-2 w-full sm:w-auto">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleSyncStatus}
                  disabled={
                    !evolutionInstanceIdForConfigStep ||
                    isSyncingStatus ||
                    isSaving
                  }
                  className="flex-1 sm:flex-none"
                  title="Verificar status da conexão com a API Evolution"
                >
                  {isSyncingStatus ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Sincronizar Status
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowQrCodeSection((prev) => !prev)}
                  disabled={!evolutionInstanceIdForConfigStep || isSaving}
                  className="flex-1 sm:flex-none"
                >
                  <QrCode className="mr-2 h-4 w-4" />
                  {showQrCodeSection ? "Ocultar QR" : "Conectar / Reconectar"}
                </Button>
              </div>
            </div>
            {showQrCodeSection && evolutionInstanceIdForConfigStep && (
              <div className="pt-4 border-t">
                <ConfigureEvolutionApiStep
                  key={evolutionInstanceIdForConfigStep} // Garante recriação se o ID mudar
                  existingInstanceId={evolutionInstanceIdForConfigStep}
                  onConnectionSuccess={handleEvolutionConnectionSuccess}
                  onStatusChange={handleEvolutionStatusChange}
                />
                {configureStepStatus !== "IDLE" &&
                  configureStepStatus !== "CONNECTED" && (
                    <div className="mt-2 text-center text-sm text-muted-foreground">
                      Tentativa de Conexão:{" "}
                      <EvolutionStatusDisplay
                        status={configureStepStatus}
                        error={configureStepError}
                      />
                    </div>
                  )}
              </div>
            )}
            {!evolutionInstanceIdForConfigStep &&
              inboxData.channel_type === "whatsapp_evolution" && (
                <Alert variant="default">
                  <Terminal className="h-4 w-4" />
                  <AlertTitle>ID da Instância Ausente</AlertTitle>
                  <AlertDescription>
                    Não é possível gerenciar a conexão porque o ID da Instância
                    Evolution associado a esta caixa de entrada não pôde ser
                    encontrado nos dados carregados.
                  </AlertDescription>
                </Alert>
              )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

interface StatusDisplayProps {
  status: EvolutionInstanceStatus | ConfigureStepStatus | null; // Usar o tipo do OpenAPI para status do DB
  error?: string | null;
}

const EvolutionStatusDisplay: React.FC<StatusDisplayProps> = ({
  status,
  error,
}) => {
  const errorTitle = error ? `Erro: ${error}` : "";

  switch (status) {
    case "CONNECTED":
      return (
        <span className="inline-flex items-center gap-1 font-medium text-green-600">
          <CheckCircle className="h-4 w-4" /> Conectado
        </span>
      );
    case "DISCONNECTED":
      return (
        <span className="inline-flex items-center gap-1 font-medium text-red-600">
          <XCircle className="h-4 w-4" /> Desconectado
        </span>
      );
    case "QRCODE": // Este é um status que o ConfigureEvolutionApiStep pode reportar internamente
    case "WAITING_SCAN": // Este também
      return (
        <span className="inline-flex items-center gap-1 font-medium text-blue-600">
          <QrCode className="h-4 w-4" /> Precisa Escanear (QR)
        </span>
      );
    case "FETCHING_QR": // Interno ao ConfigureEvolutionApiStep
      return (
        <span className="inline-flex items-center gap-1 font-medium text-blue-600">
          <Loader2 className="h-4 w-4 animate-spin" /> Carregando QR
        </span>
      );
    case "TIMEOUT": // Pode ser do ConfigureEvolutionApiStep ou do DB
      return (
        <span className="inline-flex items-center gap-1 font-medium text-orange-600">
          <Clock className="h-4 w-4" /> Tempo Esgotado
        </span>
      );
    case "SOCKET_ERROR": // Interno ao ConfigureEvolutionApiStep
      return (
        <span
          className="inline-flex items-center gap-1 font-medium text-red-600"
          title="Erro na conexão WebSocket"
        >
          <WifiOff className="h-4 w-4" /> Erro de Socket
        </span>
      );
    case "API_ERROR": // Do DB
      return (
        <span
          className="inline-flex items-center gap-1 font-medium text-red-600"
          title={errorTitle}
        >
          <Terminal className="h-4 w-4" /> Erro na API
        </span>
      );
    case "CONFIG_ERROR": // Não é um status do DB, mas pode ser do ConfigureEvolutionApiStep
      return (
        <span
          className="inline-flex items-center gap-1 font-medium text-yellow-600"
          title="Verifique a URL/API Key"
        >
          <Terminal className="h-4 w-4" /> Erro de Config.
        </span>
      );
    case "ERROR": // Genérico, pode ser do ConfigureEvolutionApiStep ou do DB
      return (
        <span
          className="inline-flex items-center gap-1 font-medium text-red-600"
          title={errorTitle}
        >
          <XCircle className="h-4 w-4" /> Erro
        </span>
      );
    case "PENDING": // Do DB
    case "CREATED": // Do DB
    case "CONNECTING": // Do DB
      return (
        <span className="inline-flex items-center gap-1 font-medium text-yellow-600">
          <Loader2 className="h-4 w-4 animate-spin" />{" "}
          {status.charAt(0).toUpperCase() + status.slice(1).toLowerCase()}
        </span>
      );
    case "UNKNOWN": // Do DB
    case "IDLE": // Interno ao ConfigureEvolutionApiStep
    case "CREATING_INSTANCE": // Interno ao ConfigureEvolutionApiStep
    default:
      return (
        <span className="inline-flex items-center gap-1 font-medium text-muted-foreground">
          Desconhecido
        </span>
      );
  }
};
