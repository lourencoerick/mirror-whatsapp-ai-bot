"use client";

import { GoogleIcon } from "@/components/icons/google-icon";
import { Button } from "@/components/ui/button";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { getGoogleAuthorizeUrl } from "@/lib/api/google-calendar";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";

export function ReauthorizeGoogleButton() {
  const [isLoading, setIsLoading] = useState(false);
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch();

  const handleReconnect = async () => {
    setIsLoading(true);
    try {
      // 1. Invalida o cache, como antes.
      await queryClient.invalidateQueries({
        queryKey: ["googleIntegrationStatus"],
      });
      // 2. Chama nosso backend para obter a URL de autorização.
      const { authorization_url } = await getGoogleAuthorizeUrl(fetcher);

      // 3. Redireciona o usuário para a URL do Google.
      if (authorization_url) {
        window.location.href = authorization_url;
      } else {
        throw new Error("Não foi possível obter a URL de autorização.");
      }
    } catch (err) {
      console.error("Erro ao iniciar a re-autorização:", err);
      setIsLoading(false);
      // Mostrar um erro para o usuário
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
