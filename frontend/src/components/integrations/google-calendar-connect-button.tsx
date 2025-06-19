// components/integrations/GoogleCalendarConnectButton.tsx
"use client";

import { useUser } from "@clerk/nextjs";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { GoogleIcon } from "@/components/icons/google-icon";
import { Button } from "@/components/ui/button";

/**
 * A button that handles the connection to Google Calendar via Clerk.
 * It shows the connection status and allows the user to initiate the OAuth flow.
 */
export function GoogleCalendarConnectButton() {
  const { isLoaded, isSignedIn, user } = useUser();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // O redirectUrl deve apontar para a página de configurações real, não a de teste.
  // Certifique-se de que esta rota está correta para sua aplicação.
  const redirectUrl = "/dashboard/settings";

  if (!isLoaded || !isSignedIn) {
    return (
      <div className="flex items-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Carregando status da conta...
      </div>
    );
  }

  const isConnected = user.externalAccounts.some(
    (acc) => acc.provider === "google"
  );

  const handleConnect = async () => {
    if (!user) return;

    setIsLoading(true);
    setError(null);
    try {
      await user.createExternalAccount({
        strategy: "oauth_google",
        redirectUrl: redirectUrl,
      });
    } catch (err) {
      console.error("Clerk OAuth error:", err);
      setError("Falha ao conectar com o Google. Tente novamente.");
      setIsLoading(false);
    }
  };

  // Se já estiver conectado, não mostramos nada. A UI pai (o formulário)
  // irá renderizar o seletor de calendário em vez deste botão.
  // Isso torna o componente mais reutilizável.
  if (isConnected) {
    return null;
  }

  return (
    <div className="flex flex-col items-start space-y-2">
      <p className="text-sm text-muted-foreground">
        Você precisa conectar sua conta do Google para continuar.
      </p>
      <Button
        type="button" // Importante para não submeter o formulário pai
        variant="outline" // Estilo visual do botão
        onClick={handleConnect}
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <GoogleIcon className="mr-2 h-4 w-4" />
        )}
        {isLoading ? "Redirecionando..." : "Conectar com Google"}
      </Button>
      {error && <p className="text-sm text-red-600 mt-1">{error}</p>}
    </div>
  );
}
