"use client";

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import * as apiKeyService from "@/lib/api/api-key";
import { ApiKeyRead } from "@/lib/api/api-key";
import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  KeyRound,
  PlusCircle,
  RefreshCw,
  Terminal,
  Trash2,
} from "lucide-react";

import { GenerateApiKeyDialog } from "./generate-api-key-dialog";
import { RevokeApiKeyDialog } from "./revoke-api-key-dialog";

interface ApiKeysManagerProps {
  inboxId: string;
}

/**
 * A self-contained component to manage API keys for a specific inbox.
 * It handles listing, generating, and revoking API keys with robust state management.
 */
export function ApiKeysManager({ inboxId }: ApiKeysManagerProps) {
  const fetcher = useAuthenticatedFetch();
  const [keys, setKeys] = useState<ApiKeyRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefetching, setIsRefetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // State for controlling the dialogs
  const [isGenerateDialogOpen, setIsGenerateDialogOpen] = useState(false);
  const [keyToRevoke, setKeyToRevoke] = useState<ApiKeyRead | null>(null);
  const [isRevokeDialogOpen, setIsRevokeDialogOpen] = useState(false);

  /**
   * Fetches or re-fetches the list of API keys from the server.
   * Manages different loading states for initial load vs. subsequent updates.
   * @param {boolean} isInitialLoad - True if it's the first load, false for updates.
   */
  const fetchApiKeys = useCallback(
    async (isInitialLoad = false) => {
      if (!inboxId) return;

      if (isInitialLoad) {
        setIsLoading(true);
      } else {
        setIsRefetching(true);
      }
      setError(null);

      try {
        const data = await apiKeyService.listApiKeys(inboxId, fetcher);
        setKeys(data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load API keys.";
        setError(message);
      } finally {
        if (isInitialLoad) {
          setIsLoading(false);
        } else {
          setIsRefetching(false);
        }
      }
    },
    [inboxId, fetcher]
  );

  // Effect for the initial data load. Runs only when inboxId changes.
  useEffect(() => {
    fetchApiKeys(true);
  }, [fetchApiKeys]);

  /**
   * Callback function passed to child dialogs after a successful action.
   * It ensures dialogs are closed and then triggers a re-fetch of the API keys.
   */
  const handleKeyListChanged = () => {
    fetchApiKeys(false); // Trigger a background refetch
  };

  /**
   * Sets the target key and opens the revoke confirmation dialog.
   * @param {ApiKeyRead} key - The API key object to be revoked.
   */
  const handleRevokeClick = (key: ApiKeyRead) => {
    setKeyToRevoke(key);
    setIsRevokeDialogOpen(true);
  };

  if (isLoading) {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardHeader>
          <Skeleton className="h-6 w-1/2 mb-2" />
          <Skeleton className="h-4 w-3/4" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="w-full max-w-2xl mx-auto">
        <CardHeader>
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <CardTitle>Integrações e Chaves de API</CardTitle>
              <CardDescription>
                Gere chaves de API para integrar esta caixa de entrada com
                outros serviços.
              </CardDescription>
            </div>
            <div className="flex gap-2 w-full sm:w-auto">
              <Button
                variant="outline"
                size="icon"
                onClick={() => fetchApiKeys(false)}
                disabled={isRefetching}
                title="Atualizar lista de chaves"
              >
                {isRefetching ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </Button>
              <Button
                onClick={() => setIsGenerateDialogOpen(true)}
                className="flex-grow"
              >
                <PlusCircle className="mr-2 h-4 w-4" />
                Gerar Nova Chave
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <Terminal className="h-4 w-4" />
              <AlertTitle>Erro ao Carregar Chaves</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-4">
            {keys.length > 0 ? (
              keys.map((key) => (
                <div
                  key={key.id}
                  className="flex items-center justify-between gap-4 p-3 border rounded-md bg-muted/50"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <KeyRound className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                    <div className="overflow-hidden">
                      <p className="font-medium truncate" title={key.name}>
                        {key.name}
                      </p>
                      <p className="text-sm text-muted-foreground font-mono">
                        {key.prefix}_...{key.last_four}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="destructive"
                    size="icon"
                    onClick={() => handleRevokeClick(key)}
                    title={`Revogar chave ${key.name}`}
                    disabled={isRefetching}
                  >
                    <Trash2 className="h-4 w-4" />
                    <span className="sr-only">Revogar</span>
                  </Button>
                </div>
              ))
            ) : (
              <div className="text-center text-sm text-muted-foreground py-8 border-2 border-dashed rounded-lg">
                Nenhuma chave de API gerada para esta caixa de entrada.
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Dialogs are rendered here but controlled by the state above */}
      <GenerateApiKeyDialog
        inboxId={inboxId}
        open={isGenerateDialogOpen}
        onOpenChange={setIsGenerateDialogOpen}
        onKeyGenerated={handleKeyListChanged}
      />

      <RevokeApiKeyDialog
        inboxId={inboxId}
        apiKey={keyToRevoke}
        open={isRevokeDialogOpen}
        onOpenChange={setIsRevokeDialogOpen}
        onKeyRevoked={handleKeyListChanged}
      />
    </>
  );
}
