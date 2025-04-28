// app/dashboard/knowledge/page.tsx
"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FileText, Globe, Loader2, Type } from "lucide-react"; // Importar mais ícones
import { useState } from "react";
import { toast } from "sonner";
import { AddUrlForm } from "./_components/add-url-form";
// --- Importar Tabela e API ---
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  deleteKnowledgeDocument,
  getKnowledgeDocuments,
} from "@/lib/api/knowledge"; // Importar get e delete
import { DocumentTable } from "./_components/document-table";

// --- Fim Importações ---

const KnowledgeBasePage = () => {
  const [isAddUrlOpen, setIsAddUrlOpen] = useState(false);
  // TODO: Adicionar estados para outros modais (Add File, Add Text)
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null); // Para feedback de deleção
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch();
  // --- Busca de Documentos com React Query ---
  const {
    data: documents = [], // Default para array vazio
    isLoading: isLoadingDocuments,
    isError: isErrorLoading,
    error: loadingError,
    refetch: refetchDocuments, // Função para recarregar
  } = useQuery({
    queryKey: ["knowledgeDocuments"], // Chave única para esta query
    queryFn: () =>
      fetcher ? getKnowledgeDocuments(fetcher) : Promise.resolve(null),

    staleTime: 5 * 60 * 1000, // Considerar dados frescos por 5 minutos
  });
  // --- Fim Busca ---

  // --- Mutação para Deletar Documento ---
  const { mutate: triggerDelete } = useMutation({
    mutationFn: (documentId: string) =>
      fetcher
        ? deleteKnowledgeDocument(fetcher, documentId)
        : Promise.resolve(null), // Função da API que deleta
    onMutate: (documentIdToDelete) => {
      // Opcional: Feedback visual imediato (antes da resposta da API)
      setIsDeletingId(documentIdToDelete);
      toast.loading(`Deleting document...`, {
        id: `delete-${documentIdToDelete}`,
      });
    },
    onSuccess: (data, documentIdToDelete) => {
      toast.success(`Document deleted successfully.`, {
        id: `delete-${documentIdToDelete}`,
      });
      // Invalidar a query para atualizar a lista na UI
      queryClient.invalidateQueries({ queryKey: ["knowledgeDocuments"] });
    },
    onError: (error: any, documentIdToDelete) => {
      console.error(`Failed to delete document ${documentIdToDelete}:`, error);
      toast.error(
        `Failed to delete document: ${error.message || "Unknown error"}`,
        { id: `delete-${documentIdToDelete}` }
      );
    },
    onSettled: (data, error, documentIdToDelete) => {
      // Remover indicador de loading independentemente do resultado
      setIsDeletingId(null);
    },
  });
  // --- Fim Mutação ---

  const handleAddFiles = () => {
    /* ... (placeholder) ... */ alert(
      'Funcionalidade "Adicionar Arquivos" ainda não implementada.'
    );
  };
  const handleCreateText = () => {
    /* ... (placeholder) ... */ alert(
      'Funcionalidade "Criar Texto" ainda não implementada.'
    );
  };

  // Função chamada pela tabela ao clicar em deletar
  const handleDeleteDocument = (documentId: string) => {
    triggerDelete(documentId); // Chamar a mutação
  };

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Knowledge Base</h1>

      {/* Seção de Ações */}
      {/* ... (Cards como antes, abrindo modais) ... */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card
          className="hover:shadow-md transition-shadow cursor-pointer"
          onClick={() => setIsAddUrlOpen(true)}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Add URL</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Import content directly from a website URL.
            </p>
          </CardContent>
        </Card>
        <Card
          className="hover:shadow-md transition-shadow cursor-pointer"
          onClick={handleAddFiles}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Add Files</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Upload documents (PDF, TXT, DOCX, etc.).
            </p>
          </CardContent>
        </Card>
        <Card
          className="hover:shadow-md transition-shadow cursor-pointer"
          onClick={handleCreateText}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Create Text</CardTitle>
            <Type className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Manually add text snippets or Q&A.
            </p>
          </CardContent>
        </Card>
      </div>
      <AddUrlForm open={isAddUrlOpen} onOpenChange={setIsAddUrlOpen} />
      {/* TODO: Adicionar Modais para Add File e Add Text */}

      {/* Seção de Busca e Filtro (Placeholder Comentado) */}
      {/* <div className="flex space-x-2">
         <input placeholder="Search Knowledge Base..." className="flex-grow px-3 py-2 border rounded-md text-sm" disabled/>
         <Button variant="outline" disabled>+ Type</Button>
      </div> */}

      {/* Seção de Listagem / Estado Vazio / Loading / Erro */}
      <div className="border rounded-lg min-h-[200px]">
        {isLoadingDocuments ? (
          <div className="flex items-center justify-center h-full p-6 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading
            documents...
          </div>
        ) : isErrorLoading ? (
          <div className="flex flex-col items-center justify-center h-full p-6 text-destructive">
            <AlertCircle className="h-8 w-8 mb-2" />
            <p className="font-semibold">Failed to load documents</p>
            <p className="text-sm text-center">
              {loadingError?.message || "An unknown error occurred."}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchDocuments()}
              className="mt-4"
            >
              Try Again
            </Button>
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-6 text-muted-foreground">
            {/* Ícone Estado Vazio */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mx-auto mb-2 text-gray-400"
            >
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <line x1="10" y1="9" x2="8" y2="9"></line>
            </svg>
            <p className="font-semibold">No documents found</p>
            <p className="text-sm">
              You haven't added any knowledge sources yet.
            </p>
          </div>
        ) : (
          // Renderizar a tabela se houver documentos
          <DocumentTable
            documents={documents}
            onDelete={handleDeleteDocument}
            isDeletingId={isDeletingId}
          />
        )}
      </div>
    </div>
  );
};

export default KnowledgeBasePage;
