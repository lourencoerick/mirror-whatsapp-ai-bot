// src/app/dashboard/knowledge/_components/add-files-form.tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react"; // Hook for referencing DOM elements
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
import { FileUp, Loader2 } from "lucide-react"; // Icons

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { addKnowledgeFile } from "@/lib/api/knowledge"; // API function
// import { KNOWLEDGE_QUERY_KEY } from "@/lib/constants"; // Query key constant
import { components } from "@/types/api"; // API type definitions
type IngestResponse = components["schemas"]["IngestResponse"];
const KNOWLEDGE_QUERY_KEY = "knowledgeDocuments";
// --- Constants for Validation ---
// Read max file size from environment variable or use default (10MB)
const MAX_FILE_SIZE =
  parseInt(process.env.NEXT_PUBLIC_MAX_UPLOAD_KB || "10240", 10) * 1024;
// Define accepted MIME types for validation
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document", // .docx
  // Add other types supported by the backend if necessary
];
// String representation of accepted extensions for display and input attribute
const ACCEPTED_EXTENSIONS_STR = ".pdf, .txt, .md, .docx";

// Zod schema for form validation (pt-BR messages)
const addFileFormSchema = z.object({
  file: z
    .instanceof(FileList)
    .refine(
      (files) => files?.length === 1,
      "É necessário selecionar um arquivo."
    ) // pt-BR
    .refine(
      (files) => files?.[0]?.size <= MAX_FILE_SIZE,
      `O tamanho máximo do arquivo é ${MAX_FILE_SIZE / 1024 / 1024}MB.` // pt-BR
    )
    .refine(
      (files) => ACCEPTED_MIME_TYPES.includes(files?.[0]?.type),
      `Tipo de arquivo não suportado. Aceitos: ${ACCEPTED_EXTENSIONS_STR}` // pt-BR
    ),
});

type AddFileFormValues = z.infer<typeof addFileFormSchema>;

interface AddFilesFormProps {
  /** Controls the visibility of the dialog. */
  open: boolean;
  /** Callback function invoked when the dialog's open state changes. */
  onOpenChange: (open: boolean) => void;
}

/**
 * A dialog form component for uploading knowledge base files.
 * Features a custom button trigger for the hidden file input.
 * Handles validation, API submission, and user feedback.
 * @param {AddFilesFormProps} props - The component props.
 */
export function AddFilesForm({ open, onOpenChange }: AddFilesFormProps) {
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch();
  const fileInputRef = useRef<HTMLInputElement>(null); // Ref for the hidden file input element

  const form = useForm<AddFileFormValues>({
    resolver: zodResolver(addFileFormSchema),
    defaultValues: {
      file: undefined,
    },
  });

  // Watch the 'file' field value to dynamically update UI elements
  const selectedFileList = form.watch("file");
  const selectedFile = selectedFileList?.[0];

  // --- Mutation for uploading file ---
  const mutation = useMutation({
    mutationFn: (file: File) => {
      if (!fetcher)
        return Promise.reject(
          new Error("Authentication context not available.")
        );
      return addKnowledgeFile(fetcher, file); // Call the API function
    },
    onMutate: async () => {
      // Display loading toast (pt-BR)
      return { toastId: toast.loading("Enviando arquivo...") };
    },
    onSuccess: (data: IngestResponse, variables, context) => {
      // Check if the API response indicates success
      if (data && data.document_id) {
        toast.success(
          `Arquivo "${
            variables.name
          }" enviado. Ingestão iniciada (ID da Tarefa: ${
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
        if (fileInputRef.current) fileInputRef.current.value = ""; // Clear the hidden input visually
        onOpenChange(false); // Close the dialog
      } else {
        throw new Error(
          "Falha ao iniciar a tarefa de ingestão. A API não retornou o resultado esperado."
        ); // pt-BR
      }
    },
    onError: (error: Error, variables, context) => {
      console.error("File upload failed:", error);
      toast.error(`Falha no envio: ${error.message || "Erro desconhecido"}`, {
        // pt-BR
        id: context?.toastId,
      });
      // Consider resetting the file input on error if desired
      // form.resetField('file');
      // if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  /** Handles form submission by triggering the mutation. */
  function onSubmit(values: AddFileFormValues) {
    if (!fetcher) {
      toast.error(
        "Não é possível enviar: Contexto de autenticação indisponível."
      ); // pt-BR
      return;
    }
    // Schema validation ensures file exists here
    if (values.file?.[0]) {
      mutation.mutate(values.file[0]);
    } else {
      // Fallback error, should ideally be caught by Zod
      toast.error("Nenhum arquivo selecionado ou arquivo inválido."); // pt-BR
    }
  }

  /** Handles dialog close actions and resets the form. */
  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) {
      form.reset(); // Reset form state
      if (fileInputRef.current) fileInputRef.current.value = ""; // Clear the hidden input visually
    }
    onOpenChange(isOpen);
  };

  /** Programmatically clicks the hidden file input element. */
  const handleSelectFileClick = () => {
    // Clear previous validation errors when user tries to select a new file
    form.clearErrors("file");
    fileInputRef.current?.click();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          {/* User-facing text translated to pt-BR */}
          <DialogTitle>Adicionar Arquivo de Conhecimento</DialogTitle>
          <DialogDescription>
            Faça upload de um arquivo ({ACCEPTED_EXTENSIONS_STR}). Ele será
            processado em breve. Tamanho máx: {MAX_FILE_SIZE / 1024 / 1024}MB.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="file" // Name matches the Zod schema field
              render={({ field }) => (
                <FormItem>
                  {/* User-facing text translated to pt-BR */}
                  <FormLabel>Arquivo</FormLabel>
                  {/* Hidden file input element */}
                  <FormControl>
                    <Input
                      ref={fileInputRef}
                      type="file"
                      accept={ACCEPTED_MIME_TYPES.join(",")} // Restrict selectable file types
                      onChange={(e) => field.onChange(e.target.files)} // Update react-hook-form state
                      className="hidden"
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  {/* Visible button that triggers the hidden input */}
                  <Button
                    type="button" // Prevent default form submission
                    variant="outline"
                    onClick={handleSelectFileClick}
                    disabled={mutation.isPending}
                    className="w-full justify-start text-left font-normal" // Mimic input appearance
                  >
                    <FileUp className="mr-2 h-4 w-4" />
                    {selectedFile ? (
                      // Display truncated filename if selected
                      <span className="truncate">{selectedFile.name}</span>
                    ) : (
                      // Default text (pt-BR)
                      "Escolher arquivo..."
                    )}
                  </Button>
                  {/* Displays validation errors */}
                  <FormMessage />
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
              <Button
                type="submit"
                disabled={!selectedFile || mutation.isPending} // Disable if no file or during submission
              >
                {mutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {/* User-facing text translated to pt-BR */}
                {mutation.isPending ? "Enviando..." : "Enviar Arquivo"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
