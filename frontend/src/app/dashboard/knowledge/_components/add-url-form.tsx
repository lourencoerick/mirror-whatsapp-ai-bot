// src/app/dashboard/knowledge/_components/add-url-form.tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query"; // Use useMutation
import { useForm } from "react-hook-form";
import { toast } from "sonner"; // For user feedback
import * as z from "zod";

import { Button } from "@/components/ui/button";
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
import { Loader2 } from "lucide-react"; // Loading icon

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { addKnowledgeUrl } from "@/lib/api/knowledge"; // API function
// import { KNOWLEDGE_QUERY_KEY } from "@/lib/constants"; // Query key constant
import { components } from "@/types/api"; // API type definitions
type IngestResponse = components["schemas"]["IngestResponse"];
const KNOWLEDGE_QUERY_KEY = "knowledgeDocuments";
// Zod schema for form validation (pt-BR message)
const addUrlFormSchema = z.object({
  url: z.string().url({
    message: "Por favor, insira uma URL válida (ex: https://exemplo.com).",
  }),
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
 * @param {AddUrlFormProps} props - The component props.
 */
export function AddUrlForm({ open, onOpenChange }: AddUrlFormProps) {
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch();

  const form = useForm<AddUrlFormValues>({
    resolver: zodResolver(addUrlFormSchema),
    defaultValues: {
      url: "",
    },
  });

  // --- Mutation for adding URL ---
  const mutation = useMutation({
    mutationFn: (url: string) => {
      if (!fetcher)
        return Promise.reject(
          new Error("Authentication context not available.")
        );
      return addKnowledgeUrl(fetcher, url);
    },
    onMutate: async () => {
      // Display loading toast and return its ID for updates
      return {
        toastId: toast.loading("Adicionando URL à Base de Conhecimento..."),
      }; // pt-BR
    },
    onSuccess: (data: IngestResponse, variables, context) => {
      // Check if the API response indicates success (adjust condition if needed)
      if (data && data.document_id) {
        toast.success(
          `URL adicionada com sucesso! Ingestão iniciada (ID da Tarefa: ${
            data.job_id || "N/A"
          }).`,
          {
            // pt-BR
            id: context?.toastId,
          }
        );
        // Invalidate the query to refresh the document list
        queryClient.invalidateQueries({ queryKey: [KNOWLEDGE_QUERY_KEY] });
        form.reset(); // Clear the form
        onOpenChange(false); // Close the dialog
      } else {
        // Handle cases where the API returns 2xx but without expected data
        throw new Error(
          "Falha ao iniciar a tarefa de ingestão. A API não retornou o resultado esperado."
        ); // pt-BR
      }
    },
    onError: (error: Error, variables, context) => {
      console.error("Failed to add URL:", error);
      toast.error(
        `Falha ao adicionar URL: ${error.message || "Erro desconhecido"}`,
        {
          // pt-BR
          id: context?.toastId,
        }
      );
    },
    // No need for explicit 'finally' block as useMutation handles pending state
  });

  /** Handles form submission by triggering the mutation. */
  function onSubmit(values: AddUrlFormValues) {
    if (!fetcher) {
      toast.error(
        "Não é possível enviar: Contexto de autenticação indisponível."
      ); // pt-BR
      return;
    }
    mutation.mutate(values.url);
  }

  /** Handles dialog close actions and resets the form. */
  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      form.reset(); // Reset form when closing
    }
    onOpenChange(isOpen);
  };

  return (
    // The Dialog component wraps the form
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          {/* User-facing text translated to pt-BR */}
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
                  {/* User-facing text translated to pt-BR */}
                  <FormLabel>URL do Site</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="https://exemplo.com/sobre-nos" // pt-BR placeholder
                      {...field}
                      disabled={mutation.isPending} // Disable input while submitting
                    />
                  </FormControl>
                  <FormMessage /> {/* Displays validation errors */}
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
                  Cancelar {/* pt-BR */}
                </Button>
              </DialogClose>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {/* User-facing text translated to pt-BR */}
                {mutation.isPending ? "Adicionando..." : "Adicionar URL"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
