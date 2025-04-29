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
import { ConversationStatusOption } from "@/types/inbox"; // Ajuste o caminho se necessário
import { ArrowLeft, Bot, Loader2, Terminal, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
/**
 * Definition of the wizard steps with PT-BR text for UI.
 * @constant
 */
const WIZARD_STEPS = [
  {
    id: 1,
    name: "Escolha o Canal",
    description: "Selecione o canal de comunicação.",
  },
  {
    id: 2,
    name: "Nomeie a Caixa de Entrada",
    description: "Dê um nome para sua Caixa de Entrada.",
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

type ChannelType = "whatsapp_evolution_api" | "whatsapp_cloud_api" | string;
interface EvolutionApiDetails {
  id: string;
  shared_api_url?: string;
  logical_token_encrypted?: string;
}
interface CloudApiDetails {
  phoneNumberId: string;
  wabaId: string;
  accessToken: string;
  verifyToken: string;
}
interface ConfiguredChannelDetails {
  evolution?: EvolutionApiDetails;
  cloud?: CloudApiDetails;
}
interface CreateInboxResponse {
  id: string;
  name: string;
  channel_type: string;
}

const DEFAULT_INITIAL_STATUS: ConversationStatusOption = "BOT";

/**
 * Page component for the multi-step wizard to create a new Inbox.
 * Guides the user through selecting a channel, naming the inbox, configuring it, and finalizing.
 * @page
 */
export default function CreateInboxPage() {
  const router = useRouter();
  const authenticatedFetch = useAuthenticatedFetch();
  const { setPageTitle } = useLayoutContext();

  // --- State Management  ---
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [selectedChannelType, setSelectedChannelType] =
    useState<ChannelType | null>(null);
  const [inboxName, setInboxName] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [configuredDetails, setConfiguredDetails] =
    useState<ConfiguredChannelDetails | null>(null);
  const [isChannelConfigValid, setIsChannelConfigValid] =
    useState<boolean>(false);
  const [isEvolutionConnected, setIsEvolutionConnected] =
    useState<boolean>(false);
  const [initialConversationStatus, setInitialConversationStatus] =
    useState<ConversationStatusOption>(DEFAULT_INITIAL_STATUS);

  // --- Set Page Title ---
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
          <h1 className="text-2xl md:text-3xl tracking-tight">
            Cria Nova Caixa de Entrada
          </h1>
        )}
      </div>
    );
  }, [setPageTitle, isLoading]);

  // --- Navigation and Callback Handlers (Logic remains, error messages in PT-BR) ---

  const handleChannelSelect = useCallback((channelType: ChannelType) => {
    setSelectedChannelType(channelType);
    setInboxName("");
    setConfiguredDetails(null);
    setIsChannelConfigValid(false);
    setIsEvolutionConnected(false);
    setFormError(null);
    setCurrentStep(2);
  }, []);

  const handleGoToConfigureStep = useCallback(() => {
    setFormError(null);
    if (!inboxName.trim()) {
      setFormError("O nome da Inbox é obrigatório.");
      return;
    }
    if (inboxName.trim().length > 100) {
      setFormError("O nome da Inbox não pode exceder 100 caracteres.");
      return;
    }
    setConfiguredDetails(null);
    setIsChannelConfigValid(false);
    setIsEvolutionConnected(false);
    setCurrentStep(3);
  }, [inboxName]);

  const handleGoToFinalStep = useCallback(() => {
    setFormError(null);
    if (!isChannelConfigValid) {
      if (
        selectedChannelType === "whatsapp_evolution_api" &&
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

  const handleChannelConfigured = useCallback(
    (details: EvolutionApiDetails | CloudApiDetails, type: ChannelType) => {
      console.log(`Details received for ${type}:`, details);
      setConfiguredDetails((prev) => ({
        ...prev,
        [type === "whatsapp_evolution_api" ? "evolution" : "cloud"]: details,
      }));
    },
    []
  );

  const handleEvolutionConnectionSuccess = useCallback(() => {
    console.log(
      "Evolution API connection successful signal received by parent."
    );
    setIsEvolutionConnected(true);
  }, []);

  const handleConfigValidityChange = useCallback((isValid: boolean) => {
    setIsChannelConfigValid(isValid);
    if (isValid) {
      setFormError(null);
    }
  }, []);

  const handleGoToPreviousStep = useCallback(() => {
    if (currentStep > 1) {
      const previousStep = currentStep - 1;
      setCurrentStep(previousStep);
      setFormError(null);
      if (currentStep === 3) {
        setConfiguredDetails(null);
        setIsChannelConfigValid(false);
        setIsEvolutionConnected(false);
      }
    }
  }, [currentStep]);

  const handleFinalSubmit = useCallback(async () => {
    setFormError(null);

    // --- Final Validation with PT-BR error messages ---
    if (!inboxName.trim()) {
      setFormError("O nome da Inbox está faltando.");
      setCurrentStep(2);
      return;
    }
    if (!selectedChannelType) {
      setFormError("O tipo de canal não foi selecionado.");
      setCurrentStep(1);
      return;
    }
    if (!configuredDetails) {
      setFormError("Os detalhes de configuração do canal estão faltando.");
      setCurrentStep(3);
      return;
    }

    let channelDetailsPayload:
      | Partial<EvolutionApiDetails>
      | Partial<CloudApiDetails> = {};
    let isValidPayload = false;

    if (
      selectedChannelType === "whatsapp_evolution_api" &&
      configuredDetails.evolution
    ) {
      channelDetailsPayload = configuredDetails.evolution;
      if (!isEvolutionConnected) {
        setFormError(
          "A API Evolution não está conectada. Por favor, complete o processo de conexão."
        );
        setCurrentStep(3);
        return;
      }
      isValidPayload = true;
    } else if (
      selectedChannelType === "whatsapp_cloud_api" &&
      configuredDetails.cloud
    ) {
      channelDetailsPayload = configuredDetails.cloud;
      if (
        !configuredDetails.cloud.phoneNumberId ||
        !configuredDetails.cloud.wabaId ||
        !configuredDetails.cloud.accessToken
      ) {
        setFormError(
          "A configuração da API Cloud está incompleta. Preencha todos os campos obrigatórios."
        );
        setCurrentStep(3);
        return;
      }
      isValidPayload = true;
    }

    if (!isValidPayload) {
      setFormError(
        "Os detalhes de configuração para o canal selecionado são inválidos ou estão faltando."
      );
      setCurrentStep(3);
      return;
    }
    // --- End Final Validation ---

    setIsLoading(true);
    const toastId = toast.loading("Criando inbox...");

    try {
      const payload = {
        name: inboxName.trim(),
        channel_type: selectedChannelType,
        channel_details: channelDetailsPayload,
      };
      console.log("Submitting payload:", payload);

      const response = await authenticatedFetch("/api/v1/inboxes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data: CreateInboxResponse | { detail: string } =
        await response.json();

      if (!response.ok) {
        const errorMessage =
          (data as { detail: string }).detail || "Falha ao criar a Inbox.";
        throw new Error(errorMessage);
      }

      const successData = data as CreateInboxResponse;
      toast.success(`Inbox "${successData.name}" criada com sucesso!`, {
        id: toastId,
        description: "Redirecionando...", // PT-BR
      });
      setTimeout(() => router.push("/dashboard/inboxes"), 3000);
    } catch (err: unknown) {
      console.error("Error creating inbox:", err);
      let errorMsg = "Ocorreu um erro inesperado.";
      if (err instanceof Error && err.message) {
        errorMsg = err.message;
      }
      toast.error("Falha na Criação", { id: toastId, description: errorMsg });
      setFormError(errorMsg);
      setIsLoading(false);
    }
  }, [
    inboxName,
    selectedChannelType,
    configuredDetails,
    isEvolutionConnected,
    authenticatedFetch,
    router,
  ]);

  // --- Render Function for Step Content (with PT-BR text) ---
  const renderStepContent = () => {
    const currentStepInfo = WIZARD_STEPS.find((s) => s.id === currentStep);
    const stepTitle = currentStepInfo?.name || "";
    const stepDescription = currentStepInfo?.description || "";

    switch (currentStep) {
      case 1: // Choose Channel
        return (
          <ChooseChannelStep
            onSelectChannel={handleChannelSelect}
            stepTitle={stepTitle} // Pass PT-BR title
            stepDescription={stepDescription} // Pass PT-BR description
          />
        );

      case 2: // Name Inbox
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
              <CardTitle>{stepTitle}</CardTitle> {/* PT-BR */}
              <CardDescription>{stepDescription}</CardDescription> {/* PT-BR */}
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                {/* PT-BR Label */}
                <Label htmlFor="inboxName">Nome da Caixa de Entrada *</Label>
                <Input
                  id="inboxName"
                  value={inboxName}
                  onChange={(e) => {
                    setInboxName(e.target.value);
                    if (formError) setFormError(null);
                  }}
                  placeholder="Ex: Equipe Vendas Principal"
                  required
                  maxLength={100}
                  disabled={isLoading}
                  aria-describedby="inboxNameHelp"
                />
                {/* PT-BR Description */}
                <p id="inboxNameHelp" className="text-sm text-muted-foreground">
                  Usado para identificar esta caixa de entrada na plataforma
                  (máx 100 caracteres).
                </p>
              </div>
              {/* Initial status selection */}
              <div className="space-y-2">
                <Label htmlFor="initialStatus">
                  Status Inicial da Conversa
                </Label>
                <Select
                  value={initialConversationStatus}
                  onValueChange={(value: ConversationStatusOption) =>
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
                  Escolha se novas conversas são inicialmente tratadas pelo robô
                  ou colocadas na fila para um agente humano.
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

      case 3: // Configure Channel
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
                {selectedChannelType === "whatsapp_evolution_api" &&
                  "Conecte sua instância da Evolution API escaneando o QR code."}
                {selectedChannelType === "whatsapp_cloud_api" &&
                  "Insira os detalhes da sua API Cloud do WhatsApp abaixo."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {selectedChannelType === "whatsapp_evolution_api" && (
                <ConfigureEvolutionApiStep
                  inboxName={inboxName}
                  onConfigured={(details) =>
                    handleChannelConfigured(details, "whatsapp_evolution_api")
                  }
                  onConnectionSuccess={handleEvolutionConnectionSuccess}
                  onValidityChange={handleConfigValidityChange}
                  isLoading={isLoading}
                />
              )}
              {selectedChannelType === "whatsapp_cloud_api" && (
                <ConfigureCloudApiStep
                  onConfigured={(details) =>
                    handleChannelConfigured(details, "whatsapp_cloud_api")
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

      case 4: // Finalize / Review
        if (!selectedChannelType || !inboxName.trim() || !configuredDetails) {
          return (
            <p className="text-destructive">
              Faltam informações obrigatórias. Por favor, volte.
            </p>
          );
        }

        let channelFriendlyName = "Desconhecido";
        if (selectedChannelType === "whatsapp_evolution_api")
          channelFriendlyName = "WhatsApp (Evolution API)"; // Keep technical name
        if (selectedChannelType === "whatsapp_cloud_api")
          channelFriendlyName = "WhatsApp (API Oficial Cloud)"; // Keep technical name

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
                  <strong>Nome da Inbox:</strong> {inboxName}
                </p>
                <p>
                  <strong>Tipo de Canal:</strong> {channelFriendlyName}
                </p>
                {selectedChannelType === "whatsapp_evolution_api" &&
                  configuredDetails.evolution && (
                    <>
                      <p>
                        <strong>ID da Instância:</strong>{" "}
                        {configuredDetails.evolution.id}
                      </p>
                      {/* <p><strong>URL da API:</strong> {configuredDetails.evolution.api_url}</p> */}
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
                      </p>{" "}
                      {/* PT-BR Status Text */}
                    </>
                  )}
                {selectedChannelType === "whatsapp_cloud_api" &&
                  configuredDetails.cloud && (
                    <>
                      <p>
                        <strong>ID do Número de Telefone:</strong>{" "}
                        {configuredDetails.cloud.phoneNumberId}
                      </p>
                      <p>
                        <strong>WABA ID:</strong>{" "}
                        {configuredDetails.cloud.wabaId}
                      </p>
                      <p>
                        <strong>Token de Verificação:</strong>{" "}
                        {configuredDetails.cloud.verifyToken ||
                          "(Não definido)"}
                      </p>{" "}
                      {/* PT-BR Status Text */}
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
                    Criando Inbox...
                  </>
                ) : (
                  "Confirmar e Criar Inbox"
                )}
              </Button>
            </CardFooter>
          </Card>
        );

      default:
        return <p className="text-muted-foreground">Passo desconhecido.</p>;
    }
  };

  // --- Main Return ---
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
