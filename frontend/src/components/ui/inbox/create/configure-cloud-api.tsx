// src/app/dashboard/inboxes/new/components/ConfigureCloudApiStep.tsx
/**
 * @fileoverview Component to collect configuration details for the WhatsApp Cloud API.
 * Part of the Inbox creation wizard (Step 3).
 */
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { components } from "@/types/api";
import { Info } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";

type CloudApiConfigPayload =
  components["schemas"]["WhatsAppCloudConfigCreateInput"];

interface CloudApiFormState {
  phone_number_id: string;
  waba_id: string;
  access_token: string;
  webhook_verify_token: string;
  app_id: string;
}

interface ConfigureCloudApiStepProps {
  onConfigured: (details: CloudApiConfigPayload) => void;
  onValidityChange: (isValid: boolean) => void;
  isLoading?: boolean;
}

export const ConfigureCloudApiStep: React.FC<ConfigureCloudApiStepProps> = ({
  onConfigured,
  onValidityChange,
  isLoading = false,
}) => {
  const [config, setConfig] = useState<CloudApiFormState>({
    phone_number_id: "",
    waba_id: "",
    access_token: "",
    webhook_verify_token: "",
    app_id: "",
  });
  const [isMounted, setIsMounted] = useState(false);

  const suggestedVerifyToken = useMemo(() => {
    return `wa-verify-token-${Math.random().toString(36).substring(2, 15)}`;
  }, []);

  useEffect(() => {
    if (config.webhook_verify_token === "") {
      setConfig((prev) => ({
        ...prev,
        webhook_verify_token: suggestedVerifyToken,
      }));
    }
    setIsMounted(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestedVerifyToken]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setConfig((prev) => ({ ...prev, [name]: value }));
  };

  useEffect(() => {
    if (!isMounted) return;

    const isValid =
      config.phone_number_id.trim() !== "" &&
      config.waba_id.trim() !== "" &&
      config.access_token.trim() !== "" &&
      config.webhook_verify_token.trim() !== "";

    onValidityChange(isValid);

    if (isValid) {
      const finalPayload: CloudApiConfigPayload = {
        phone_number_id: config.phone_number_id.trim(),
        waba_id: config.waba_id.trim(),
        access_token: config.access_token.trim(),
        webhook_verify_token: config.webhook_verify_token.trim(),
        app_id: config.app_id?.trim() || null,
      };
      onConfigured(finalPayload);
    }
  }, [config, onConfigured, onValidityChange, isMounted]);

  const webhookBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const webhookUrlPlaceholder = `${webhookBaseUrl}/api/v1/webhooks/whatsapp/cloud/{SEU_PHONE_NUMBER_ID}`; // String para placeholder
  const webhookUrlDynamic = config.phone_number_id
    ? `${webhookBaseUrl}/api/v1/webhooks/whatsapp/cloud/${config.phone_number_id}`
    : webhookUrlPlaceholder;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="phone_number_id">ID do Número de Telefone *</Label>
        <Input
          id="phone_number_id"
          name="phone_number_id"
          value={config.phone_number_id}
          onChange={handleChange}
          required
          disabled={isLoading}
          placeholder="Ex: 109876543210987"
        />
        <p className="text-sm text-muted-foreground">
          Encontrado na configuração do seu App Meta.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="waba_id">ID da Conta Empresarial (WABA ID) *</Label>
        <Input
          id="waba_id"
          name="waba_id"
          value={config.waba_id}
          onChange={handleChange}
          required
          disabled={isLoading}
          placeholder="Ex: 210987654321098"
        />
        <p className="text-sm text-muted-foreground">
          O ID da sua conta do WhatsApp Business.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="access_token">Token de Acesso Permanente *</Label>
        <Input
          id="access_token"
          name="access_token"
          type="password"
          value={config.access_token}
          onChange={handleChange}
          required
          disabled={isLoading}
          placeholder="Cole seu token aqui"
        />
        <p className="text-sm text-muted-foreground">
          Recomenda-se usar um Token de Usuário do Sistema que não expira.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="webhook_verify_token">
          Token de Verificação do Webhook *
        </Label>
        <Input
          id="webhook_verify_token"
          name="webhook_verify_token"
          value={config.webhook_verify_token}
          onChange={handleChange}
          required
          disabled={isLoading}
          placeholder={suggestedVerifyToken}
        />
        <p className="text-sm text-muted-foreground">
          Uma string secreta para verificar webhooks. Use a sugestão ou crie a
          sua.
        </p>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription className="text-xs">
          Configure a seguinte URL de Webhook no seu App Meta (na seção WhatsApp{" "}
          {">"} Configuração) e use o Token de Verificação definido acima:
          <code className="mt-1 block break-all rounded bg-muted px-2 py-1 font-mono text-xs">
            {webhookUrlDynamic}
          </code>
          {config.phone_number_id ? (
            ""
          ) : (
            <span className="text-destructive">
              Substitua &#123;SEU_PHONE_NUMBER_ID&#125; pelo ID do seu número de
              telefone.
            </span>
          )}
          <br />
          Assine os eventos de `messages`.
        </AlertDescription>
      </Alert>
    </div>
  );
};
