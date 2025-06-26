"use client";

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import * as apiKeyService from "@/lib/api/api-key";
import { ApiKeyRead } from "@/lib/api/api-key";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

interface RevokeApiKeyDialogProps {
  inboxId: string;
  apiKey: ApiKeyRead | null; // A chave a ser revogada
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onKeyRevoked: () => void; // Callback para notificar o pai
}

export function RevokeApiKeyDialog({
  inboxId,
  apiKey,
  open,
  onOpenChange,
  onKeyRevoked,
}: RevokeApiKeyDialogProps) {
  const fetcher = useAuthenticatedFetch();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRevoke = async () => {
    if (!apiKey) return;

    setIsSubmitting(true);
    const toastId = toast.loading("Revogando chave de API...");

    try {
      await apiKeyService.revokeApiKey(inboxId, apiKey.id, fetcher);
      toast.success("Chave de API revogada com sucesso!", { id: toastId });
      onKeyRevoked(); // Notifica o pai para atualizar a lista
      onOpenChange(false); // Fecha o diálogo
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Falha ao revogar a chave.";
      toast.error(message, { id: toastId });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Você tem certeza?</AlertDialogTitle>
          <AlertDialogDescription>
            Esta ação não pode ser desfeita. Isso irá revogar permanentemente a
            chave de API{" "}
            <span className="font-bold font-mono">
              {apiKey?.name} ({apiKey?.prefix}_...{apiKey?.last_four})
            </span>
            . Qualquer integração usando esta chave deixará de funcionar.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleRevoke}
            disabled={isSubmitting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Sim, Revogar Chave
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
