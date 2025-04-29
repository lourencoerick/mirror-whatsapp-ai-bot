// src/app/dashboard/knowledge/_components/add-text-form.tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
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
import { Textarea } from "@/components/ui/textarea"; // Textarea component
import { Loader2 } from "lucide-react"; // Loading icon

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { addKnowledgeText } from "@/lib/api/knowledge"; // API function
// import { KNOWLEDGE_QUERY_KEY } from "@/lib/constants"; // Query key constant
import { components } from "@/types/api"; // API type definitions
type IngestResponse = components["schemas"]["IngestResponse"];
const KNOWLEDGE_QUERY_KEY = "knowledgeDocuments";
// Zod schema for form validation (pt-BR messages)
const addTextFormSchema = z.object({
  title: z
    .string()
    .min(3, "O título deve ter pelo menos 3 caracteres.")
    .max(150, "O título não pode exceder 150 caracteres."),
  content: z
    .string()
    .min(10, "O conteúdo deve ter pelo menos 10 caracteres.")
    .max(20000, "Conteúdo muito longo. Limite de 20.000 caracteres."), // Increased limit slightly, adjust if needed
  // description: z.string().max(255, 'Descrição não pode exceder 255 caracteres.').optional(), // Optional description field
});

type AddTextFormValues = z.infer<typeof addTextFormSchema>;

interface AddTextFormProps {
  /** Controls the visibility of the dialog. */
  open: boolean;
  /** Callback function invoked when the dialog's open state changes. */
  onOpenChange: (open: boolean) => void;
}

/**
 * A dialog form component for adding a new knowledge source via direct text input.
 * Handles input validation, API submission, and user feedback.
 * @param {AddTextFormProps} props - The component props.
 */
export function AddTextForm({ open, onOpenChange }: AddTextFormProps) {
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch();

  const form = useForm<AddTextFormValues>({
    resolver: zodResolver(addTextFormSchema),
    defaultValues: {
      title: "",
      content: "",
      // description: "",
    },
  });

  // --- Mutation for adding text ---
  const mutation = useMutation({
    mutationFn: (data: AddTextFormValues) => {
      if (!fetcher)
        return Promise.reject(
          new Error("Authentication context not available.")
        );
      // Call API function (currently without description)
      return addKnowledgeText(fetcher, data.title, data.content);
    },
    onMutate: async () => {
      // Display loading toast (pt-BR)
      return { toastId: toast.loading("Criando entrada de texto...") };
    },
    onSuccess: (data: IngestResponse, variables, context) => {
      // Check if the API response indicates success
      if (data && data.document_id) {
        toast.success(
          `Entrada de texto "${
            variables.title
          }" criada. Ingestão iniciada (ID da Tarefa: ${
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
        throw new Error(
          "Falha ao iniciar a tarefa de ingestão. A API não retornou o resultado esperado."
        ); // pt-BR
      }
    },
    onError: (error: Error, variables, context) => {
      console.error("Text entry creation failed:", error);
      toast.error(`Falha na criação: ${error.message || "Erro desconhecido"}`, {
        // pt-BR
        id: context?.toastId,
      });
    },
  });

  /** Handles form submission by triggering the mutation. */
  function onSubmit(values: AddTextFormValues) {
    if (!fetcher) {
      toast.error(
        "Não é possível enviar: Contexto de autenticação indisponível."
      ); // pt-BR
      return;
    }
    mutation.mutate(values);
  }

  /** Handles dialog close actions and resets the form. */
  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      form.reset(); // Reset form when closing
    }
    onOpenChange(isOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[525px]">
        {" "}
        {/* Slightly wider for textarea */}
        <DialogHeader>
          {/* User-facing text translated to pt-BR */}
          <DialogTitle>Criar Entrada de Texto</DialogTitle>
          <DialogDescription>
            Adicione conhecimento diretamente como texto. Forneça um título e o
            conteúdo abaixo.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  {/* User-facing text translated to pt-BR */}
                  <FormLabel>Título</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Ex: Resumo da Política de Reembolso" // pt-BR placeholder
                      {...field}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  <FormMessage /> {/* Displays validation errors */}
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="content"
              render={({ field }) => (
                <FormItem>
                  {/* User-facing text translated to pt-BR */}
                  <FormLabel>Conteúdo</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Digite o conteúdo do conhecimento aqui..." // pt-BR placeholder
                      className="min-h-[150px] resize-y" // Allow vertical resize
                      {...field}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  <FormMessage /> {/* Displays validation errors */}
                </FormItem>
              )}
            />
            {/* Optional Description Field (Commented out) */}
            {/*
                         <FormField ... >
                            <FormLabel>Descrição (Opcional)</FormLabel>
                            ...
                         </FormField>
                        */}
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
                {mutation.isPending ? "Criando..." : "Criar Entrada"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
