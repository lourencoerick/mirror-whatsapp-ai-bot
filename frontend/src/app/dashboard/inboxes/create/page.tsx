// src/app/dashboard/inboxes/create/page.tsx
"use client";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ChooseChannelStep } from "@/components/ui/inbox/create/choose-channel-step";
import { ConfigureCloudApiStep } from "@/components/ui/inbox/create/configure-cloud-api";
import { ConfigureEvolutionApiStep } from "@/components/ui/inbox/create/configure-evolution-api";
import { StepIndicator } from "@/components/ui/inbox/create/step-indicator";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { ArrowLeft, Bot, Loader2, Terminal, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { createInbox } from "@/lib/api/inbox";
import { components } from "@/types/api";

type EvolutionConfigData =
  components["schemas"]["EvolutionChannelDetailsInput"];
type CloudConfigData = components["schemas"]["WhatsAppCloudConfigCreateInput"];

interface ConfiguredChannelData {
  evolution?: EvolutionConfigData;
  cloud?: CloudConfigData;
}

type CreatableChannelType = Exclude<
  components["schemas"]["ChannelTypeEnum"],
  "simulation"
>;
type ConversationStatus = components["schemas"]["ConversationStatusEnum"];
type InboxCreatePayload = components["schemas"]["InboxCreate"];

const WIZARD_STEPS = [
  {
    id: 1,
    name: "Escolha o Canal",
    description: "Selecione o canal de comunicação.",
  },
  {
    id: 2,
    name: "Detalhes da Caixa de Entrada",
    description: "Defina o nome e configurações básicas.",
  },
  {
    id: 3,
    name: "Configure o Canal",
    description: "Conecte ou configure os detalhes do canal.",
  },
  {
    id: 4,
    name: "Finalizar",
    description: "Revise e complete a configuração.",
  },
];

const DEFAULT_INITIAL_STATUS: ConversationStatus = "BOT";

export default function CreateInboxPage() {
  const router = useRouter();
  const authenticatedFetch = useAuthenticatedFetch();
  const { setPageTitle } = useLayoutContext();

  const [currentStep, setCurrentStep] = useState<number>(1);
  const [selectedChannelType, setSelectedChannelType] =
    useState<CreatableChannelType | null>(null);
  const [inboxName, setInboxName] = useState<string>("");
  const [initialConversationStatus, setInitialConversationStatus] =
    useState<ConversationStatus>(DEFAULT_INITIAL_STATUS);
  const [enableAutoAssignment, setEnableAutoAssignment] =
    useState<boolean>(true);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [configuredChannelData, setConfiguredChannelData] =
    useState<ConfiguredChannelData | null>(null);
  const [isChannelConfigValid, setIsChannelConfigValid] =
    useState<boolean>(false);
  const [isEvolutionConnected, setIsEvolutionConnected] =
    useState<boolean>(false);

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
          <span className="font-semibold text-md">Carregando...</span>
        ) : (
          "Criar Nova Caixa de Entrada"
        )}
      </div>
    );
  }, [setPageTitle, isLoading]);

  const handleChannelSelect = useCallback(
    (channelType: CreatableChannelType) => {
      setSelectedChannelType(channelType);
      setInboxName("");
      setInitialConversationStatus(DEFAULT_INITIAL_STATUS);
      setEnableAutoAssignment(true);
      setConfiguredChannelData(null);
      setIsChannelConfigValid(false);
      setIsEvolutionConnected(false);
      setFormError(null);
      setCurrentStep(2);
    },
    []
  );

  const handleGoToConfigureStep = useCallback(() => {
    setFormError(null);
    if (!inboxName.trim()) {
      setFormError("O nome da Caixa de Entrada é obrigatório.");
      return;
    }
    if (inboxName.trim().length > 100) {
      setFormError(
        "O nome da Caixa de Entrada não pode exceder 100 caracteres."
      );
      return;
    }
    setConfiguredChannelData(null);
    setIsChannelConfigValid(false);
    setIsEvolutionConnected(false);
    setCurrentStep(3);
  }, [inboxName]);

  const handleGoToFinalStep = useCallback(() => {
    setFormError(null);
    // Não há mais lógica específica para 'simulation' aqui
    if (!isChannelConfigValid) {
      if (
        selectedChannelType === "whatsapp_evolution" &&
        !isEvolutionConnected
      ) {
        setFormError(
          "Por favor, complete o processo de conexão do WhatsApp (escaneie o QR code)."
        );
      } else {
        setFormError(
          "A configuração do canal está incompleta ou inválida. Verifique os detalhes."
        );
      }
      return;
    }
    setCurrentStep(4);
  }, [isChannelConfigValid, selectedChannelType, isEvolutionConnected]);

  const handleChannelDataConfigured = useCallback(
    (
      data: EvolutionConfigData | CloudConfigData,
      type: CreatableChannelType
    ) => {
      console.log(`Dados configurados para ${type}:`, data);
      if (type === "whatsapp_evolution") {
        setConfiguredChannelData({
          evolution: data as EvolutionConfigData,
        });
      } else if (type === "whatsapp_cloud") {
        setConfiguredChannelData({ cloud: data as CloudConfigData });
      }
    },
    []
  );

  const handleEvolutionConnectionSuccess = useCallback(() => {
    setIsEvolutionConnected(true);
    setIsChannelConfigValid(true);
    if (formError) setFormError(null);
  }, [formError]);

  const handleConfigValidityChange = useCallback(
    (isValid: boolean) => {
      setIsChannelConfigValid(isValid);
      if (isValid && formError) {
        setFormError(null);
      }
    },
    [formError]
  );

  const handleGoToPreviousStep = useCallback(() => {
    if (currentStep > 1) {
      const previousStep = currentStep - 1;
      setCurrentStep(previousStep);
      setFormError(null);
      if (currentStep === 3 || (currentStep === 2 && previousStep === 1)) {
        setConfiguredChannelData(null);
        setIsChannelConfigValid(false);
        setIsEvolutionConnected(false);
      }
      if (currentStep === 2 && previousStep === 1) {
        setSelectedChannelType(null);
        setInboxName("");
      }
    }
  }, [currentStep]);

  const handleFinalSubmit = useCallback(async () => {
    setFormError(null);
    if (!inboxName.trim()) {
      setFormError("O nome da Caixa de Entrada está faltando.");
      setCurrentStep(2);
      return;
    }
    if (!selectedChannelType) {
      setFormError("O tipo de canal não foi selecionado.");
      setCurrentStep(1);
      return;
    }

    const payload: InboxCreatePayload = {
      name: inboxName.trim(),
      channel_type: selectedChannelType,
      initial_conversation_status: initialConversationStatus,
      enable_auto_assignment: enableAutoAssignment,
    };

    if (selectedChannelType === "whatsapp_evolution") {
      if (!configuredChannelData?.evolution?.platform_instance_id) {
        setFormError(
          "Configuração da Evolution API incompleta ou ID da instância faltando."
        );
        setCurrentStep(3);
        return;
      }
      if (!isEvolutionConnected) {
        setFormError(
          "A API Evolution não está conectada. Por favor, escaneie o QR code."
        );
        setCurrentStep(3);
        return;
      }
      payload.evolution_instance_to_link = configuredChannelData.evolution;
    } else if (selectedChannelType === "whatsapp_cloud") {
      if (!configuredChannelData?.cloud) {
        setFormError("Configuração da Cloud API faltando.");
        setCurrentStep(3);
        return;
      }
      const cloudConfig = configuredChannelData.cloud;
      if (
        !cloudConfig.phone_number_id ||
        !cloudConfig.waba_id ||
        !cloudConfig.access_token ||
        !cloudConfig.webhook_verify_token
      ) {
        setFormError("Campos obrigatórios da Cloud API não preenchidos.");
        setCurrentStep(3);
        return;
      }
      payload.whatsapp_cloud_config_to_create = cloudConfig;
    } else {
      setFormError("Tipo de canal inválido para criação manual.");
      setCurrentStep(1);
      return;
    }

    setIsLoading(true);
    const toastId = toast.loading("Criando caixa de entrada...");

    try {
      const newInbox = await createInbox(payload, authenticatedFetch);
      toast.success(`Caixa de entrada "${newInbox.name}" criada com sucesso!`, {
        id: toastId,
        description: "Redirecionando...",
      });
      setTimeout(() => router.push("/dashboard/inboxes"), 2000);
    } catch (err: unknown) {
      console.error("Erro ao criar caixa de entrada:", err);
      const errorMsg =
        err instanceof Error ? err.message : "Ocorreu um erro inesperado.";
      toast.error("Falha na Criação", { id: toastId, description: errorMsg });
      setFormError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [
    inboxName,
    selectedChannelType,
    initialConversationStatus,
    enableAutoAssignment,
    configuredChannelData,
    isEvolutionConnected,
    authenticatedFetch,
    router,
  ]);

  const renderStepContent = () => {
    const currentStepInfo = WIZARD_STEPS.find((s) => s.id === currentStep);
    const stepTitle = currentStepInfo?.name || "";
    const stepDescription = currentStepInfo?.description || "";

    switch (currentStep) {
      case 1:
        return (
          <ChooseChannelStep
            onSelectChannel={
              handleChannelSelect as (
                channelType: components["schemas"]["ChannelTypeEnum"]
              ) => void
            }
            stepTitle={stepTitle}
            stepDescription={stepDescription}
          />
        );
      case 2:
        // ... (conteúdo do passo 2 permanece o mesmo)
        if (!selectedChannelType) {
          return (
            <p className="text-destructive">
              Por favor, volte e selecione um canal primeiro.
            </p>
          );
        }
        return (
          <Card className="w-full max-w-2xl">
            <CardHeader>
              <CardTitle>{stepTitle}</CardTitle>
              <CardDescription>{stepDescription}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="inboxName">Nome da Caixa de Entrada *</Label>
                <Input
                  id="inboxName"
                  value={inboxName}
                  onChange={(e) => {
                    setInboxName(e.target.value);
                    if (formError) setFormError(null);
                  }}
                  placeholder="Ex: Vendas Principal"
                  required
                  maxLength={100}
                  disabled={isLoading}
                  aria-describedby="inboxNameHelp"
                />
                <p id="inboxNameHelp" className="text-sm text-muted-foreground">
                  Usado para identificar esta caixa de entrada (máx 100
                  caracteres).
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="initialStatus">
                  Status Inicial da Conversa
                </Label>
                <Select
                  value={initialConversationStatus}
                  onValueChange={(value: ConversationStatus) =>
                    setInitialConversationStatus(value)
                  }
                  disabled={isLoading}
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
                <p
                  id="initialStatusHelp"
                  className="text-sm text-muted-foreground"
                >
                  Status padrão para novas conversas nesta caixa de entrada.
                </p>
              </div>
              {formError && (
                <Alert variant="destructive" className="mt-4">
                  <AlertDescription>{formError}</AlertDescription>
                </Alert>
              )}
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button
                type="button"
                variant="outline"
                onClick={handleGoToPreviousStep}
                disabled={isLoading}
              >
                Voltar
              </Button>
              <Button
                type="button"
                onClick={handleGoToConfigureStep}
                disabled={
                  isLoading ||
                  !inboxName.trim() ||
                  inboxName.trim().length > 100
                }
              >
                Próximo
              </Button>
            </CardFooter>
          </Card>
        );
      case 3:
        if (!selectedChannelType || !inboxName.trim()) {
          return (
            <p className="text-destructive">
              Faltando seleção de canal ou nome da inbox. Por favor, volte.
            </p>
          );
        }

        return (
          <Card className="w-full max-w-2xl">
            <CardHeader>
              <CardTitle>{stepTitle}</CardTitle>
              <CardDescription>
                {selectedChannelType === "whatsapp_evolution" &&
                  "Conecte sua instância da Evolution API escaneando o QR code."}
                {selectedChannelType === "whatsapp_cloud" &&
                  "Insira os detalhes da sua API Cloud do WhatsApp abaixo."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {selectedChannelType === "whatsapp_evolution" && (
                <ConfigureEvolutionApiStep
                  inboxName={inboxName}
                  onConfigured={(details) =>
                    handleChannelDataConfigured(
                      { platform_instance_id: details?.id },
                      "whatsapp_evolution"
                    )
                  }
                  onConnectionSuccess={handleEvolutionConnectionSuccess}
                  onValidityChange={handleConfigValidityChange}
                  isLoading={isLoading}
                />
              )}
              {selectedChannelType === "whatsapp_cloud" && (
                <ConfigureCloudApiStep
                  onConfigured={(details) =>
                    handleChannelDataConfigured(details, "whatsapp_cloud")
                  }
                  onValidityChange={handleConfigValidityChange}
                  isLoading={isLoading}
                />
              )}
              {formError && (
                <Alert variant="destructive" className="mt-4">
                  <AlertDescription>{formError}</AlertDescription>
                </Alert>
              )}
            </CardContent>
            <CardFooter className="flex justify-between mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={handleGoToPreviousStep}
                disabled={isLoading}
              >
                Voltar
              </Button>

              <Button
                type="button"
                onClick={handleGoToFinalStep}
                disabled={isLoading || !isChannelConfigValid}
              >
                Próximo
              </Button>
            </CardFooter>
          </Card>
        );
      case 4:
        if (
          !selectedChannelType ||
          !inboxName.trim() ||
          !configuredChannelData
        ) {
          return (
            <p className="text-destructive">
              Faltam informações obrigatórias. Por favor, volte.
            </p>
          );
        }
        let channelFriendlyName = "Desconhecido";
        if (selectedChannelType === "whatsapp_evolution")
          channelFriendlyName = "WhatsApp (Evolution API)";
        if (selectedChannelType === "whatsapp_cloud")
          channelFriendlyName = "WhatsApp (API Oficial Cloud)";

        return (
          <Card className="w-full max-w-2xl">
            <CardHeader>
              <CardTitle>{stepTitle}</CardTitle>
              <CardDescription>{stepDescription}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <h3 className="mb-2 text-lg font-medium">Revise os Detalhes:</h3>
              <div className="space-y-1 rounded-md border bg-muted/50 p-4 text-sm">
                <p>
                  <strong>Nome da Caixa de Entrada:</strong> {inboxName}
                </p>
                <p>
                  <strong>Tipo de Canal:</strong> {channelFriendlyName}
                </p>
                <p>
                  <strong>Status Inicial da Conversa:</strong>{" "}
                  {initialConversationStatus}
                </p>
                <p>
                  <strong>Atribuição Automática:</strong>{" "}
                  {enableAutoAssignment ? "Habilitada" : "Desabilitada"}
                </p>

                {selectedChannelType === "whatsapp_evolution" &&
                  configuredChannelData?.evolution && (
                    <>
                      <p>
                        <strong>ID da Instância Evolution:</strong>{" "}
                        {configuredChannelData.evolution.platform_instance_id}
                      </p>
                      <p>
                        <strong>Status da Conexão:</strong>{" "}
                        <span
                          className={
                            isEvolutionConnected
                              ? "text-green-600"
                              : "text-destructive"
                          }
                        >
                          {isEvolutionConnected ? "Conectado" : "Não Conectado"}
                        </span>
                      </p>
                    </>
                  )}
                {selectedChannelType === "whatsapp_cloud" &&
                  configuredChannelData?.cloud && (
                    <>
                      <p>
                        <strong>ID do Número de Telefone:</strong>{" "}
                        {configuredChannelData.cloud.phone_number_id}
                      </p>
                      <p>
                        <strong>WABA ID:</strong>{" "}
                        {configuredChannelData.cloud.waba_id}
                      </p>
                      <p>
                        <strong>Token de Verificação:</strong>{" "}
                        {configuredChannelData.cloud.webhook_verify_token}
                      </p>
                      {configuredChannelData.cloud.app_id && (
                        <p>
                          <strong>App ID:</strong>{" "}
                          {configuredChannelData.cloud.app_id}
                        </p>
                      )}
                    </>
                  )}
              </div>
              {formError && (
                <Alert variant="destructive">
                  <Terminal className="h-4 w-4" />
                  <AlertTitle>Erro</AlertTitle>
                  <AlertDescription>{formError}</AlertDescription>
                </Alert>
              )}
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button
                type="button"
                variant="outline"
                onClick={handleGoToPreviousStep}
                disabled={isLoading}
              >
                Voltar
              </Button>
              <Button
                type="button"
                onClick={handleFinalSubmit}
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Criando...
                  </>
                ) : (
                  "Confirmar e Criar"
                )}
              </Button>
            </CardFooter>
          </Card>
        );
      default:
        return <p className="text-muted-foreground">Passo desconhecido.</p>;
    }
  };

  return (
    <div className="px-4 pb-8 pt-2 md:px-6 md:pt-4 lg:px-8">
      <div className="flex flex-col gap-8 md:flex-row lg:gap-12">
        <div className="w-full md:w-60 lg:w-72 md:flex-shrink-0">
          <StepIndicator steps={WIZARD_STEPS} currentStepId={currentStep} />
        </div>
        <div className="min-w-0 flex-grow">{renderStepContent()}</div>
      </div>
    </div>
  );
}
