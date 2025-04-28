// app/dashboard/knowledge/page.tsx
"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  deleteKnowledgeDocument,
  getKnowledgeDocuments,
} from "@/lib/api/knowledge";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FileText, Globe, Loader2, Type } from "lucide-react";
import { useMemo, useState } from "react"; // Adicionar useMemo
import { toast } from "sonner";
import { AddUrlForm } from "./_components/add-url-form";
import { DocumentTable } from "./_components/document-table";
// --- Importar Componente de Paginação (ASSUMINDO QUE EXISTE) ---
import { PaginationControls } from "@/components/ui/pagination-controls"; // Ajuste o caminho!
// --- Importar Tipos ---
import { components } from "@/types/api"; // API type definitions
// type KnowledgeDocumentRead = components["schemas"]["KnowledgeDocumentRead"];
type PaginatedKnowledgeDocumentRead =
  components["schemas"]["PaginatedKnowledgeDocumentRead"];

// Assumir que a API retorna algo como KnowledgeDocumentList ou similar
// Se a API retornar apenas a lista, precisaremos de outra chamada para o total
// Vamos assumir por agora que a API retorna { items: KnowledgeDocumentRead[], total: number }

// --- Constante para Itens por Página ---
const ITEMS_PER_PAGE = 10;

const KnowledgeBasePage = () => {
  const [isAddUrlOpen, setIsAddUrlOpen] = useState(false);
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null);
  // --- Estado para Paginação ---
  const [currentPage, setCurrentPage] = useState(1);
  // --- Fim Estado Paginação ---

  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch(); // Assumindo que este hook fornece o fetcher autenticado

  // --- Busca de Documentos com Paginação ---
  const {
    data: paginatedData, // Renomear para indicar que é paginado
    isLoading: isLoadingDocuments,
    isError: isErrorLoading,
    error: loadingError,
    refetch: refetchDocuments,
  } = useQuery({
    // Chave da query inclui a página atual para refetch automático na mudança
    queryKey: ["knowledgeDocuments", currentPage, ITEMS_PER_PAGE],
    queryFn: async (): Promise<PaginatedKnowledgeDocumentRead | null> => {
      if (!fetcher) return null;
      const skip = (currentPage - 1) * ITEMS_PER_PAGE;
      // Chamar a função da API passando skip e limit
      // Ajuste getKnowledgeDocuments para aceitar skip/limit
      return getKnowledgeDocuments(fetcher, skip, ITEMS_PER_PAGE);
    },
    staleTime: 5 * 60 * 1000,
    keepPreviousData: true, // Útil para manter dados antigos visíveis enquanto carrega a próxima página
  });
  // --- Fim Busca ---

  // Calcular total de páginas
  const totalPages = useMemo(() => {
    if (!paginatedData?.total) return 0;
    return Math.ceil(paginatedData.total / ITEMS_PER_PAGE);
  }, [paginatedData?.total]);

  // --- Mutação para Deletar (como antes) ---
  const { mutate: triggerDelete } = useMutation({
    mutationFn: (documentId: string) =>
      fetcher
        ? deleteKnowledgeDocument(fetcher, documentId)
        : Promise.resolve(null),
    onMutate: (id) => {
      setIsDeletingId(id);
      toast.loading(`Deleting...`, { id: `delete-${id}` });
    },
    onSuccess: (data, id) => {
      toast.success(`Document deleted.`, { id: `delete-${id}` });
      queryClient.invalidateQueries({ queryKey: ["knowledgeDocuments"] });
    },
    onError: (err: any, id) => {
      console.error(`Failed delete ${id}:`, err);
      toast.error(`Failed: ${err.message || "Unknown error"}`, {
        id: `delete-${id}`,
      });
    },
    onSettled: () => {
      setIsDeletingId(null);
    },
  });
  // --- Fim Mutação ---

  const handleAddFiles = () => {
    alert('Funcionalidade "Adicionar Arquivos" ainda não implementada.');
  };
  const handleCreateText = () => {
    alert('Funcionalidade "Criar Texto" ainda não implementada.');
  };
  const handleDeleteDocument = (documentId: string) => {
    triggerDelete(documentId);
  };

  // --- Handler para Mudança de Página ---
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
      // O useQuery refaz a busca automaticamente porque currentPage está na queryKey
    }
  };
  // --- Fim Handler ---

  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8 space-y-6 flex flex-col h-full">
      <h1 className="text-3xl font-bold tracking-tight">Knowledge Base</h1>

      {/* Seção de Ações */}
      {/* ... (Cards como antes) ... */}
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

      {/* Seção de Busca e Filtro (Placeholder Comentado) */}
      {/* ... */}

      {/* Seção de Listagem / Estado Vazio / Loading / Erro */}
      {/* Adicionado flex-grow e flex para ocupar espaço e permitir que a paginação fique no final */}
      <div className="border rounded-lg flex flex-col flex-grow">
        {isLoadingDocuments && !paginatedData ? ( // Mostrar loading inicial
          <div className="flex items-center justify-center flex-grow p-6 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading
            documents...
          </div>
        ) : isErrorLoading ? (
          <div className="flex flex-col items-center justify-center flex-grow p-6 text-destructive">
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
        ) : !paginatedData || paginatedData.items.length === 0 ? ( // Checar items.length
          <div className="flex flex-col items-center justify-center flex-grow p-6 text-muted-foreground">
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
          // Adicionado overflow-auto para permitir scroll da tabela se necessário
          <div className="overflow-auto">
            <DocumentTable
              documents={paginatedData.items} // Passar apenas os items da página atual
              onDelete={handleDeleteDocument}
              isDeletingId={isDeletingId}
            />
          </div>
        )}
        {/* --- Controles de Paginação --- */}
        {paginatedData &&
          paginatedData.total > ITEMS_PER_PAGE &&
          totalPages > 1 && (
            <PaginationControls
              currentPage={currentPage}
              totalItems={paginatedData.total}
              itemsPerPage={ITEMS_PER_PAGE}
              onPageChange={handlePageChange} // Passar o handler
              totalPages={totalPages} // Passar total de páginas calculado
              className="border-t bg-background p-4" // Ajustar estilo conforme necessário
            />
          )}
        {/* --- Fim Controles --- */}
      </div>
    </div>
  );
};

export default KnowledgeBasePage;
