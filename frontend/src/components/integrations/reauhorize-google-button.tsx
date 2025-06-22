"use client";

import { GoogleIcon } from "@/components/icons/google-icon";
import { Button } from "@/components/ui/button";
import { useUser } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";

export function ReauthorizeGoogleButton() {
  const { user } = useUser();
  const [isLoading, setIsLoading] = useState(false);
  const queryClient = useQueryClient();

  const handleReconnect = async () => {
    if (!user) return;
    const googleAccount = user.externalAccounts.find(
      (ea) => ea.provider === "google"
    );
    if (!googleAccount) {
      console.error("Conta Google não encontrada");
      return;
    }
    await queryClient.invalidateQueries({
      queryKey: ["googleIntegrationStatus"],
    });

    setIsLoading(true);
    try {
      const reauth = await googleAccount.reauthorize({
        redirectUrl: "/dashboard/settings",
        additionalScopes: [
          "https://www.googleapis.com/auth/calendar.events",
          "https://www.googleapis.com/auth/calendar.readonly",
        ],
        oidcPrompt: "consent",
      });
      if (reauth.verification?.externalVerificationRedirectURL) {
        window.location.href =
          reauth.verification.externalVerificationRedirectURL.href;
      }
    } catch (err) {
      console.error("Erro no reauthorize:", err);
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
