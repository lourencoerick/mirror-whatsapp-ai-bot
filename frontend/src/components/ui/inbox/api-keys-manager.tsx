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
import { KeyRound, PlusCircle, Terminal, Trash2 } from "lucide-react";

import { GenerateApiKeyDialog } from "./generate-api-key-dialog";
import { RevokeApiKeyDialog } from "./revoke-api-key-dialog";

interface ApiKeysManagerProps {
  inboxId: string;
}

/**
 * A self-contained component to manage API keys for a specific inbox.
 * It handles listing, generating, and revoking API keys.
 */
export function ApiKeysManager({ inboxId }: ApiKeysManagerProps) {
  const fetcher = useAuthenticatedFetch();
  const [keys, setKeys] = useState<ApiKeyRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // State for controlling the dialogs
  const [isGenerateDialogOpen, setIsGenerateDialogOpen] = useState(false);
  const [keyToRevoke, setKeyToRevoke] = useState<ApiKeyRead | null>(null);
  const [isRevokeDialogOpen, setIsRevokeDialogOpen] = useState(false);

  /**
   * Fetches the list of API keys from the server and updates the component's state.
   */
  const fetchApiKeys = useCallback(async () => {
    if (!inboxId) return;
    // Only show the main skeleton on the very first load.
    if (keys.length === 0) setIsLoading(true);
    setError(null);
    try {
      const data = await apiKeyService.listApiKeys(inboxId, fetcher);
      setKeys(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load API keys.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [inboxId, fetcher, keys.length]);

  // Initial data fetch when the component mounts.
  useEffect(() => {
    fetchApiKeys();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inboxId]); // We only want this to run when inboxId changes.

  /**
   * Callback function passed to child dialogs.
   * It triggers a re-fetch of the API keys to update the list.
   */
  const handleKeyListChanged = () => {
    fetchApiKeys();
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
            <Button
              onClick={() => setIsGenerateDialogOpen(true)}
              className="w-full sm:w-auto"
            >
              <PlusCircle className="mr-2 h-4 w-4" />
              Gerar Nova Chave
            </Button>
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
