"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import * as apiKeyService from "@/lib/api/api-key";
import { ApiKeyReadWithSecret } from "@/lib/api/api-key";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";

// Schema de validação para o formulário
const formSchema = z.object({
  name: z.string().min(3, "O nome deve ter pelo menos 3 caracteres.").max(50),
});

interface GenerateApiKeyDialogProps {
  inboxId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onKeyGenerated: () => void; // Callback para notificar o pai
}

export function GenerateApiKeyDialog({
  inboxId,
  open,
  onOpenChange,
  onKeyGenerated,
}: GenerateApiKeyDialogProps) {
  const fetcher = useAuthenticatedFetch();
  const [step, setStep] = useState<"form" | "success">("form");
  const [generatedKey, setGeneratedKey] = useState<ApiKeyReadWithSecret | null>(
    null
  );

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: "" },
  });

  // Reseta o estado do diálogo quando ele é fechado
  useEffect(() => {
    if (!open) {
      setTimeout(() => {
        form.reset();
        setStep("form");
        setGeneratedKey(null);
      }, 200); // Pequeno delay para a animação de fechamento
    }
  }, [open, form]);

  async function onSubmit(values: z.infer<typeof formSchema>) {
    const toastId = toast.loading("Gerando chave de API...");
    try {
      const payload = {
        name: values.name,
        scopes: ["sheets:trigger"], // Hardcoded por enquanto
      };
      const newKey = await apiKeyService.generateApiKey(
        inboxId,
        payload,
        fetcher
      );
      setGeneratedKey(newKey);
      setStep("success");
      onKeyGenerated(); // Notifica o componente pai para atualizar a lista
      toast.success("Chave de API gerada com sucesso!", { id: toastId });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Falha ao gerar a chave.";
      toast.error(message, { id: toastId });
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {step === "form" && (
          <>
            <DialogHeader>
              <DialogTitle>Gerar Nova Chave de API</DialogTitle>
              <DialogDescription>
                Dê um nome para sua chave para identificá-la. Ela terá permissão
                para iniciar conversas a partir de integrações.
              </DialogDescription>
            </DialogHeader>
            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nome da Chave</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="Ex: Planilha de Vendas Q1"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => onOpenChange(false)}
                    disabled={form.formState.isSubmitting}
                  >
                    Cancelar
                  </Button>
                  <Button type="submit" disabled={form.formState.isSubmitting}>
                    {form.formState.isSubmitting && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Gerar Chave
                  </Button>
                </DialogFooter>
              </form>
            </Form>
          </>
        )}

        {step === "success" && generatedKey && (
          <>
            <DialogHeader>
              <DialogTitle>Chave Gerada com Sucesso</DialogTitle>
            </DialogHeader>
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Atenção!</AlertTitle>
              <AlertDescription>
                Esta é a sua chave secreta. Por segurança, você não poderá vê-la
                novamente. Copie e guarde-a em um local seguro.
              </AlertDescription>
            </Alert>
            <div className="flex items-center gap-2 mt-4">
              <Input
                readOnly
                value={generatedKey.raw_key}
                className="font-mono"
              />
              <CopyButton valueToCopy={generatedKey.raw_key} />
            </div>
            <DialogFooter className="mt-4">
              <DialogClose asChild>
                <Button>Fechar</Button>
              </DialogClose>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
