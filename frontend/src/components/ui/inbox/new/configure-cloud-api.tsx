// src/app/dashboard/inboxes/new/components/ConfigureCloudApiStep.tsx
/**
 * @fileoverview Component to collect configuration details for the WhatsApp Cloud API.
 * Part of the Inbox creation wizard (Step 3).
 */
import React, { useState, useEffect, useMemo } from 'react';
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert"; // For displaying webhook URL
import { Info } from 'lucide-react'; // Icon for informational alert

/**
 * Interface for Cloud API configuration details. (Remains in English)
 */
interface CloudApiConfig {
    phoneNumberId: string;
    wabaId: string;
    accessToken: string;
    verifyToken: string
}

interface ConfigureCloudApiStepProps {
    /** Callback to send the configured details back to the parent component. */
    onConfigured: (details: CloudApiConfig) => void;
    /** Function to signal validity change to the parent. */
    onValidityChange: (isValid: boolean) => void;
    /** Optional: Disable fields while the parent is processing. */
    isLoading?: boolean;
}

/**
 * Renders the form fields for configuring the WhatsApp Cloud API.
 * Used within Step 3 of the Inbox creation wizard.
 * @component
 * @param {ConfigureCloudApiStepProps} props - Component props.
 */
export const ConfigureCloudApiStep: React.FC<ConfigureCloudApiStepProps> = ({
    onConfigured,
    onValidityChange,
    isLoading = false
}) => {
    const [config, setConfig] = useState<CloudApiConfig>({
        phoneNumberId: '',
        wabaId: '',
        accessToken: '',
        verifyToken: '',
    });
    const [isMounted, setIsMounted] = useState(false); // To prevent initial validation call

    // Generate a suggested verify token (user can override)
    const suggestedVerifyToken = useMemo(() => {
        return `wa-verify-token-${Math.random().toString(36).substring(2, 15)}`;
    }, []);

    // Set verify token initially if empty
    useEffect(() => {
        if (!config.verifyToken) {
            setConfig(prev => ({ ...prev, verifyToken: suggestedVerifyToken }));
        }
        setIsMounted(true); // Mark as mounted after initial setup
    }, [suggestedVerifyToken]);


    // Update internal state when an input field changes
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setConfig(prev => ({ ...prev, [name]: value }));
    };

    // Effect to validate and call onConfigured/onValidityChange when necessary data is present
    useEffect(() => {
        if (!isMounted) return; // Don't run validation on initial mount

        const isValid = config.phoneNumberId.trim() !== '' &&
                        config.wabaId.trim() !== '' &&
                        config.accessToken.trim() !== '';

        onValidityChange(isValid);

        if (isValid) {
             const finalConfig = {
                 ...config,
                 verifyToken: config.verifyToken.trim() || suggestedVerifyToken,
             };
            onConfigured(finalConfig);
        }
    }, [config, onConfigured, onValidityChange, suggestedVerifyToken, isMounted]);


    // ATTENTION: Get this base URL from the backend or an environment variable.
    const webhookBaseUrl = process.env.NEXT_PUBLIC_WEBHOOK_BASE_URL || "http://localhost:8000";
    const webhookUrl = `${webhookBaseUrl}/api/v1/webhooks/whatsapp/cloud`;

    return (
        <div className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="phoneNumberId">ID do Número de Telefone *</Label>
                <Input
                    id="phoneNumberId"
                    name="phoneNumberId"
                    value={config.phoneNumberId}
                    onChange={handleChange}
                    required
                    disabled={isLoading}
                    placeholder="Ex: 109876543210987"
                />
                <p className="text-sm text-muted-foreground">Encontrado na configuração do seu App Meta.</p>
            </div>

            <div className="space-y-2">
                <Label htmlFor="wabaId">ID da Conta Empresarial (WABA ID) *</Label>
                <Input
                    id="wabaId"
                    name="wabaId"
                    value={config.wabaId}
                    onChange={handleChange}
                    required
                    disabled={isLoading}
                    placeholder="Ex: 210987654321098"
                 />
                 <p className="text-sm text-muted-foreground">O ID da sua conta do WhatsApp Business.</p>
            </div>

            <div className="space-y-2">
                <Label htmlFor="accessToken">Token de Acesso Permanente *</Label>
                <Input
                    id="accessToken"
                    name="accessToken"
                    type="password" // Hide the token value
                    value={config.accessToken}
                    onChange={handleChange}
                    required
                    disabled={isLoading}
                    placeholder="Cole seu token aqui"
                 />
                 <p className="text-sm text-muted-foreground">Recomenda-se usar um Token de Usuário do Sistema que não expira.</p>
            </div>

            <div className="space-y-2">
                <Label htmlFor="verifyToken">Token de Verificação do Webhook</Label>
                <Input
                    id="verifyToken"
                    name="verifyToken"
                    value={config.verifyToken}
                    onChange={handleChange}
                    disabled={isLoading}
                    placeholder={suggestedVerifyToken}
                 />
                 <p className="text-sm text-muted-foreground">Uma string secreta para verificar webhooks. Use a sugestão ou crie a sua.</p>
            </div>

            {/* Webhook Information with PT-BR text */}
            <Alert>
                 <Info className="h-4 w-4" />
                 <AlertDescription className="text-xs">
                     Configure a seguinte URL de Webhook no seu App Meta (na seção WhatsApp > Configuração) e use o Token de Verificação definido acima:
                     <code className="mt-1 block break-all rounded bg-muted px-2 py-1 font-mono text-xs">
                         {webhookUrl}
                     </code>
                     Assine os eventos de `messages`.
                 </AlertDescription>
            </Alert>
        </div>
    );
};