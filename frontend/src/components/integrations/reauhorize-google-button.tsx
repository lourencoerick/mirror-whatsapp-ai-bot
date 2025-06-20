// components/integrations/ReauthorizeGoogleButton.tsx
"use client";

import { useUser } from "@clerk/nextjs";
import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";

import { GoogleIcon } from "@/components/icons/google-icon";
import { Button } from "@/components/ui/button";

/**
 * A component that prompts the user to re-authorize Google connection
 * to grant missing permissions (like calendar access).
 */
export function ReauthorizeGoogleButton() {
  const { user } = useUser();
  const [isLoading, setIsLoading] = useState(false);

  const handleReconnect = async () => {
    if (!user) return;
    setIsLoading(true);
    try {
      // Chamar a mesma função de conexão força o fluxo de re-consentimento
      // para obter os novos escopos de calendário.
      await user.createExternalAccount({
        strategy: "oauth_google",
        redirectUrl: "/dashboard/settings", // Deve ser a mesma URL
      });
    } catch (err) {
      console.error("Clerk OAuth re-auth error:", err);
      // O erro será tratado no componente pai se necessário
      setIsLoading(false);
    }
  };

  return (
    <div className="p-3 border border-yellow-300 bg-yellow-50 rounded-md space-y-2">
      <div className="flex items-center font-medium text-yellow-800">
        <AlertCircle className="h-5 w-5 mr-2" />
        Permissão Adicional Necessária
      </div>
      <p className="text-sm text-yellow-700">
        Sua conta do Google está conectada, mas precisamos da sua permissão para
        acessar seu calendário. Por favor, re-autorize a conexão.
      </p>
      <Button
        type="button"
        variant="outline"
        onClick={handleReconnect}
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <GoogleIcon className="mr-2 h-4 w-4" />
        )}
        {isLoading ? "Redirecionando..." : "Re-autorizar Conexão"}
      </Button>
    </div>
  );
}
