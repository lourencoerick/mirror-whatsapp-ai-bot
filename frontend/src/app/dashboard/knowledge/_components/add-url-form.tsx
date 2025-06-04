// src/app/dashboard/knowledge/_components/add-url-form.tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox"; // Import Checkbox
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
  FormDescription, // Import FormDescription
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { addKnowledgeUrl } from "@/lib/api/knowledge";
import { components } from "@/types/api";
type IngestResponse = components["schemas"]["IngestResponse"];
// Assuming AddUrlRequest schema from backend is { url: string, recursive: boolean }
type AddUrlApiPayload = components["schemas"]["AddUrlRequest"];

const KNOWLEDGE_QUERY_KEY = "knowledgeDocuments";

// Zod schema for form validation (pt-BR messages)
const addUrlFormSchema = z.object({
  url: z.string().url({
    message: "Por favor, insira uma URL válida (ex: https://exemplo.com).",
  }),
  recursive: z.boolean().default(false).optional(), // Add recursive field
});

type AddUrlFormValues = z.infer<typeof addUrlFormSchema>;

interface AddUrlFormProps {
  /** Controls the visibility of the dialog. */
  open: boolean;
  /** Callback function invoked when the dialog's open state changes. */
  onOpenChange: (open: boolean) => void;
}

/**
 * A dialog form component for adding a new knowledge source via URL.
 * Handles input validation, API submission, and user feedback.
 * Allows optional recursive fetching of linked pages.
 * @param {AddUrlFormProps} props - The component props.
 */
export function AddUrlForm({ open, onOpenChange }: AddUrlFormProps) {
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch();

  const form = useForm<AddUrlFormValues>({
    resolver: zodResolver(addUrlFormSchema),
    defaultValues: {
      url: "",
      recursive: false, // Default recursive to false
    },
  });

  const isRecursiveEnabled = form.watch("recursive"); // Watch the recursive field

  // --- Mutation for adding URL ---
  const mutation = useMutation({
    mutationFn: (payload: AddUrlApiPayload) => {
      // Payload is now an object
      if (!fetcher) {
        return Promise.reject(
          new Error("Authentication context not available.")
        );
      }
      return addKnowledgeUrl(fetcher, payload);
    },
    onMutate: async () => {
      return {
        toastId: toast.loading("Adicionando URL à Base de Conhecimento..."),
      };
    },
    onSuccess: (data: IngestResponse, variables, context) => {
      if (data && data.document_id) {
        const recursiveMessage = variables.recursive
          ? " (com varredura recursiva)"
          : "";
        toast.success(
          `URL adicionada com sucesso! Ingestão iniciada${recursiveMessage} (ID da Tarefa: ${
            data.job_id || "N/A"
          }).`,
          {
            id: context?.toastId,
          }
        );
        queryClient.invalidateQueries({ queryKey: [KNOWLEDGE_QUERY_KEY] });
        form.reset();
        onOpenChange(false);
      } else {
        throw new Error(
          "Falha ao iniciar a tarefa de ingestão. A API não retornou o resultado esperado."
        );
      }
    },
    onError: (error: Error, variables, context) => {
      console.error("Failed to add URL:", error);
      toast.error(
        `Falha ao adicionar URL: ${error.message || "Erro desconhecido"}`,
        {
          id: context?.toastId,
        }
      );
    },
  });

  /** Handles form submission by triggering the mutation. */
  function onSubmit(values: AddUrlFormValues) {
    if (!fetcher) {
      toast.error(
        "Não é possível enviar: Contexto de autenticação indisponível."
      );
      return;
    }
    // Ensure recursive is explicitly passed, even if undefined (backend default is false)
    const payload: AddUrlApiPayload = {
      url: values.url,
      recursive: values.recursive || false,
    };
    mutation.mutate(payload);
  }

  /** Handles dialog close actions and resets the form. */
  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      form.reset();
    }
    onOpenChange(isOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Adicionar URL à Base de Conhecimento</DialogTitle>
          <DialogDescription>
            Insira a URL de uma página web para ingerir seu conteúdo. O sistema
            irá buscar e processar o texto da página.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>URL do Site</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="https://exemplo.com/sobre-nos"
                      {...field}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="recursive"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>Varredura Recursiva</FormLabel>
                    <FormDescription>
                      Buscar e ingerir páginas vinculadas a partir desta URL
                      (mesmo domínio, profundidade 1).
                    </FormDescription>
                    {isRecursiveEnabled && (
                      <p className="text-sm text-muted-foreground pt-1">
                        <strong>Atenção:</strong> Isso pode aumentar o tempo de
                        processamento e o número de documentos ingeridos.
                      </p>
                    )}
                  </div>
                </FormItem>
              )}
            />

            <DialogFooter>
              <DialogClose asChild>
                <Button
                  type="button"
                  variant="outline"
                  disabled={mutation.isPending}
                >
                  Cancelar
                </Button>
              </DialogClose>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {mutation.isPending ? "Adicionando..." : "Adicionar URL"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
