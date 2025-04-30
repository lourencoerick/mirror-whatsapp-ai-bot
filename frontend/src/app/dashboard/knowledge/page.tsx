/* eslint-disable @typescript-eslint/no-explicit-any */
// src/app/dashboard/knowledge/page.tsx
"use client";

import { useLayoutContext } from "@/contexts/layout-context";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertCircle,
  Files,
  FileText,
  Globe,
  Loader2,
  Type,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

// --- UI Components ---
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PaginationControls } from "@/components/ui/pagination-controls"; // Assuming this exists

// --- Custom Hooks & API ---
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import {
  deleteKnowledgeDocument,
  getKnowledgeDocuments,
} from "@/lib/api/knowledge";
// import { KNOWLEDGE_QUERY_KEY } from "@/lib/constants"; // Query key constant

// --- Child Components ---
import { AddFilesForm } from "./_components/add-files-form";
import { AddTextForm } from "./_components/add-text-form";
import { AddUrlForm } from "./_components/add-url-form";
import { DocumentTable } from "./_components/document-table";

// --- Types ---
import { components } from "@/types/api";
type PaginatedKnowledgeDocumentRead =
  components["schemas"]["PaginatedKnowledgeDocumentRead"];
type KnowledgeDocumentRead = components["schemas"]["KnowledgeDocumentRead"]; // Needed for polling logic and table

// --- Constants ---
const ITEMS_PER_PAGE = 10; // Number of documents per page
const POLLING_INTERVAL = 5000; // Interval in ms for checking document status (5 seconds)
const KNOWLEDGE_QUERY_KEY = "knowledgeDocuments";

/**
 * Main page component for managing the Knowledge Base.
 * Displays action cards to add sources, a table listing existing documents
 * with pagination, and handles data fetching, mutations (delete), and status polling.
 */
const KnowledgeBasePage = () => {
  const { setPageTitle } = useLayoutContext();

  useEffect(() => {
    setPageTitle(
      <h1 className="text-2xl md:text-3xl tracking-tight">
        Base de Conhecimento
      </h1>
    );
  }, [setPageTitle]);

  // --- State ---
  const [isAddUrlOpen, setIsAddUrlOpen] = useState(false);
  const [isAddFilesOpen, setIsAddFilesOpen] = useState(false);
  const [isAddTextOpen, setIsAddTextOpen] = useState(false);
  const [isDeletingId, setIsDeletingId] = useState<string | null>(null); // Track which document is being deleted
  const [currentPage, setCurrentPage] = useState(1); // Current page for pagination

  // --- Hooks ---
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch(); // Hook for making authenticated API calls

  // --- Data Fetching Query (React Query) ---
  const {
    data: paginatedData,
    isLoading: isLoadingDocuments, // Initial loading state
    isError: isErrorLoading,
    error: loadingError,
    refetch: refetchDocuments, // Function to manually trigger refetch
    isFetching, // Indicates background fetching (including polling)
  } = useQuery({
    // Query key includes page and items per page for unique caching
    queryKey: [KNOWLEDGE_QUERY_KEY, currentPage, ITEMS_PER_PAGE],
    queryFn: async (): Promise<PaginatedKnowledgeDocumentRead | null> => {
      if (!fetcher) return null; // Don't fetch if authentication context isn't ready
      const skip = (currentPage - 1) * ITEMS_PER_PAGE;
      return getKnowledgeDocuments(fetcher, skip, ITEMS_PER_PAGE); // Call API
    },
    enabled: !!fetcher, // Only run the query if the fetcher is available
    staleTime: 1 * 60 * 1000, // Data is considered fresh for 1 minute
    placeholderData: keepPreviousData, // Keep displaying old data while fetching new page
    refetchInterval: (query) => {
      // Check if any document in the current view is pending or processing
      const data = query.state.data as
        | PaginatedKnowledgeDocumentRead
        | null
        | undefined;
      // Ensure status check is case-insensitive and handles potential nulls
      const hasPendingOrProcessing = data?.items?.some(
        (doc: KnowledgeDocumentRead) =>
          doc.status?.toUpperCase() === "PENDING" ||
          doc.status?.toUpperCase() === "PROCESSING"
      );
      // Enable polling only if there are active jobs
      return hasPendingOrProcessing ? POLLING_INTERVAL : false;
    },
    refetchIntervalInBackground: true, // Continue polling even if the browser tab is not active
  });

  // --- Derived State (Memoized) ---
  const totalPages = useMemo(() => {
    if (!paginatedData?.total) return 0;
    return Math.ceil(paginatedData.total / ITEMS_PER_PAGE);
  }, [paginatedData?.total]);

  const documents = useMemo(
    () => paginatedData?.items ?? [],
    [paginatedData?.items]
  );

  // --- Delete Mutation (React Query) ---
  const { mutate: triggerDelete } = useMutation({
    mutationFn: (documentId: string) => {
      if (!fetcher)
        return Promise.reject(
          new Error("Authentication context not available.")
        );
      return deleteKnowledgeDocument(fetcher, documentId); // Call API
    },
    onMutate: (id) => {
      setIsDeletingId(id); // Set deleting state for visual feedback
      // Display loading toast (pt-BR)
      return {
        toastId: toast.loading(`Excluindo documento...`, {
          id: `delete-${id}`,
        }),
      };
    },
    onSuccess: (data, id, context) => {
      toast.success(`Documento excluído com sucesso.`, {
        id: context?.toastId,
      }); // pt-BR
      // Invalidate the query to refetch the updated list
      queryClient.invalidateQueries({ queryKey: [KNOWLEDGE_QUERY_KEY] });
      // Optional: Adjust page if the last item on a page > 1 was deleted
      if (
        currentPage > 1 &&
        documents.length === 1 &&
        totalPages === currentPage
      ) {
        setCurrentPage((prev) => Math.max(1, prev - 1));
      }
    },
    onError: (err: any, id, context) => {
      console.error(`Failed to delete document ${id}:`, err);
      toast.error(`Falha ao excluir: ${err.message || "Erro desconhecido"}`, {
        // pt-BR
        id: context?.toastId,
      });
    },
    onSettled: () => {
      setIsDeletingId(null); // Clear deleting state regardless of outcome
    },
  });

  // --- Event Handlers ---
  /** Triggers the delete mutation for a given document ID. */
  const handleDeleteDocument = (documentId: string) => {
    // The confirmation is handled within the DocumentTable's AlertDialog
    triggerDelete(documentId);
  };

  /** Updates the current page state for pagination. */
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages && newPage !== currentPage) {
      setCurrentPage(newPage);
      // query will refetch automatically due to `currentPage` in queryKey
    }
  };

  // --- Render Logic ---
  return (
    <div className="container mx-auto p-4 md:p-6 lg:p-8 space-y-6 flex flex-col h-full">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        {/* Title (pt-BR) */}
        {/* <h1 className="text-3xl font-bold tracking-tight">
          Base de Conhecimento
        </h1> */}
        {/* Subtle loading indicator for background fetches/polling */}
        {isFetching && !isLoadingDocuments && (
          <Loader2
            className="h-5 w-5 animate-spin text-muted-foreground"
            aria-label="Atualizando…"
            role="status"
          />
        )}
      </div>

      {/* Action Cards Section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Add URL Card */}
        <Card
          className="hover:shadow-md transition-shadow cursor-pointer"
          onClick={() => setIsAddUrlOpen(true)}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            {/* Card Title/Description (pt-BR) */}
            <CardTitle className="text-sm font-medium">Adicionar URL</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Importar conteúdo diretamente de uma URL de site.
            </p>
          </CardContent>
        </Card>
        {/* Add Files Card */}
        <Card
          className="hover:shadow-md transition-shadow cursor-pointer"
          onClick={() => setIsAddFilesOpen(true)}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            {/* Card Title/Description (pt-BR) */}
            <CardTitle className="text-sm font-medium">
              Adicionar Arquivos
            </CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Fazer upload de documentos (PDF, TXT, DOCX, etc.).
            </p>
          </CardContent>
        </Card>
        {/* Create Text Card */}
        <Card
          className="hover:shadow-md transition-shadow cursor-pointer"
          onClick={() => setIsAddTextOpen(true)}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            {/* Card Title/Description (pt-BR) */}
            <CardTitle className="text-sm font-medium">Criar Texto</CardTitle>
            <Type className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Adicionar manualmente trechos de texto ou Perguntas e Respostas.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Render Dialog Forms (controlled by state) */}
      <AddUrlForm open={isAddUrlOpen} onOpenChange={setIsAddUrlOpen} />
      <AddFilesForm open={isAddFilesOpen} onOpenChange={setIsAddFilesOpen} />
      <AddTextForm open={isAddTextOpen} onOpenChange={setIsAddTextOpen} />

      {/* Document List Section */}
      <div className="border rounded-lg flex flex-col flex-grow min-h-[400px]">
        {" "}
        {/* Ensure minimum height */}
        {/* Conditional Rendering: Loading, Error, Empty, or Data Table */}
        {isLoadingDocuments && !paginatedData ? (
          // Initial Loading State (pt-BR)
          <div className="flex items-center justify-center flex-grow p-6 text-muted-foreground">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Carregando
            documentos...
          </div>
        ) : isErrorLoading ? (
          // Error State (pt-BR)
          <div className="flex flex-col items-center justify-center flex-grow p-6 text-destructive">
            <AlertCircle className="h-8 w-8 mb-2" />
            <p className="font-semibold">Falha ao carregar documentos</p>
            <p className="text-sm text-center max-w-md">
              {loadingError instanceof Error
                ? loadingError.message
                : "Ocorreu um erro desconhecido."}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchDocuments()} // Allow user to retry fetch
              className="mt-4"
              disabled={isFetching} // Disable retry button while fetching
            >
              {isFetching ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}{" "}
              Tentar Novamente
            </Button>
          </div>
        ) : documents.length === 0 ? (
          // Empty State (pt-BR)
          <div className="flex flex-col items-center justify-center flex-grow p-6 text-muted-foreground">
            {/* Empty state icon */}
            <Files
              className="h-12 w-12 mx-auto mb-4 text-gray-400"
              strokeWidth={1}
            />
            <p className="font-semibold text-lg mb-1">
              Nenhum documento encontrado
            </p>
            <p className="text-sm text-center">
              Sua base de conhecimento está vazia. <br /> Adicione fontes usando
              os cards acima.
            </p>
          </div>
        ) : (
          // Data Table Display
          <div className="overflow-auto">
            {" "}
            {/* Allow table scroll if needed */}
            <DocumentTable
              documents={documents} // Pass documents for the current page
              onDelete={handleDeleteDocument}
              isDeletingId={isDeletingId}
              isPolling={isFetching && !isLoadingDocuments} // Indicate background activity
            />
          </div>
        )}
        {/* Pagination Controls - Render only if more than one page exists */}
        {totalPages > 1 && (
          <PaginationControls
            currentPage={currentPage}
            totalItems={paginatedData?.total ?? 0}
            itemsPerPage={ITEMS_PER_PAGE}
            onPageChange={handlePageChange}
            totalPages={totalPages}
            className="border-t bg-background p-4 mt-auto" // Style to stick to the bottom
          />
        )}
      </div>
    </div>
  );
};

export default KnowledgeBasePage;
