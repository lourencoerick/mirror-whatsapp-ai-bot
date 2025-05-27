// src/app/admin/beta-requests/page.tsx
"use client";

import { Badge } from "@/components/ui/badge";
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
import { ScrollArea } from "@/components/ui/scroll-area";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { components } from "@/types/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  BetaRequestRow,
  columns,
  getStatusBadgeVariant,
  getStatusIcon,
} from "./columns";
import { BetaRequestsDataTable } from "./data-table";

type AdminBetaListResponse =
  components["schemas"]["AdminBetaTesterListResponse"];
type AdminBetaActionResponse = components["schemas"]["AdminBetaActionResponse"];

// Query key for the list of beta requests
const ADMIN_BETA_REQUESTS_QUERY_KEY = "adminBetaRequests";

/**
 * @file Admin page for managing beta access requests.
 * @returns {JSX.Element} The admin beta requests page component.
 */
export default function AdminBetaRequestsPage() {
  const { setPageTitle } = useLayoutContext();
  const fetcher = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  // State to track which item is being approved/denied for UI feedback
  const [processingAction, setProcessingAction] = useState<{
    email: string;
    type: "approve" | "deny";
  } | null>(null);

  const [selectedRequest, setSelectedRequest] = useState<BetaRequestRow | null>(
    null
  );
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  useEffect(() => {
    setPageTitle?.("Admin - Gerenciar Solicitações Beta");
  }, [setPageTitle]);

  const {
    data: betaRequestsData,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<AdminBetaListResponse, Error>({
    queryKey: [ADMIN_BETA_REQUESTS_QUERY_KEY], // Consider adding filters/pagination to the key if API supports them
    queryFn: async () => {
      if (!fetcher) throw new Error("Fetcher not available");
      // TODO: Add pagination and filter parameters to the API call
      const response = await fetcher(
        "/api/v1/admin/beta/requests?page=1&size=50" // Initial example, consider making dynamic
      );
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({})); // Graceful catch if JSON parsing fails
        throw new Error(
          errorData.detail || `Failed to fetch requests: ${response.statusText}`
        );
      }
      return response.json();
    },
    enabled: !!fetcher, // Ensures fetcher is available before attempting to query
  });

  const approveMutation = useMutation<AdminBetaActionResponse, Error, string>({
    mutationFn: (email: string) => {
      if (!fetcher) throw new Error("Fetcher not available");
      setProcessingAction({ email, type: "approve" });
      return fetcher(`/api/v1/admin/beta/requests/${email}/approve`, {
        method: "POST",
      }).then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha ao aprovar."); // User message in PT-BR
        return data;
      });
    },
    onSuccess: (data) => {
      toast.success("Solicitação Aprovada!", { description: data.message });
      queryClient.invalidateQueries({
        queryKey: [ADMIN_BETA_REQUESTS_QUERY_KEY],
      });
    },
    onError: (error) => {
      toast.error("Erro ao Aprovar", { description: error.message });
    },
    onSettled: () => {
      setProcessingAction(null); // Clear processing state regardless of outcome
    },
  });

  const denyMutation = useMutation<AdminBetaActionResponse, Error, string>({
    mutationFn: (email: string) => {
      if (!fetcher) throw new Error("Fetcher not available");
      setProcessingAction({ email, type: "deny" });
      return fetcher(`/api/v1/admin/beta/requests/${email}/deny`, {
        method: "POST",
      }).then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha ao negar."); // User message in PT-BR
        return data;
      });
    },
    onSuccess: (data) => {
      toast.info("Solicitação Negada.", { description: data.message });
      queryClient.invalidateQueries({
        queryKey: [ADMIN_BETA_REQUESTS_QUERY_KEY],
      });
    },
    onError: (error) => {
      toast.error("Erro ao Negar", { description: error.message });
    },
    onSettled: () => {
      setProcessingAction(null); // Clear processing state
    },
  });

  const handleApprove = (email: string) => {
    approveMutation.mutate(email);
  };

  const handleDeny = (email: string) => {
    denyMutation.mutate(email);
  };

  const handleViewDetails = (request: BetaRequestRow) => {
    setSelectedRequest(request);
    setIsDetailModalOpen(true);
  };

  // Memoize columns to prevent unnecessary re-renders of the data table
  // Re-created if processingAction changes to update button states (disabled/loading)
  const memoizedColumns = useMemo(
    () =>
      columns(
        handleApprove,
        handleDeny,
        handleViewDetails,
        (email) =>
          processingAction?.type === "approve" &&
          processingAction?.email === email,
        (email) =>
          processingAction?.type === "deny" && processingAction?.email === email
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [processingAction] // Dependencies: handleApprove, handleDeny, handleViewDetails are stable due to useCallback/definition scope
  );

  const handleRefresh = () => {
    toast.info("Atualizando lista de solicitações...");
    refetch(); // Calls the refetch function from useQuery
  };

  // Display full-page loader only on initial load
  if (isLoading && !isRefetching) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="ml-4">Carregando solicitações beta...</p>
      </div>
    );
  }

  // Display full-page error only on initial load error
  if (isError && !isRefetching) {
    return (
      <div className="container mx-auto p-4 text-center">
        <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
        <h2 className="text-xl font-semibold text-red-700">
          Erro ao Carregar Solicitações
        </h2>
        <p className="text-muted-foreground">
          {(error as Error)?.message || "Ocorreu um problema."}
        </p>
        <Button onClick={handleRefresh} className="mt-4">
          <RefreshCw className="mr-2 h-4 w-4" />
          Tentar Novamente
        </Button>
      </div>
    );
  }

  const dataToDisplay = betaRequestsData?.items || [];

  /**
   * @description A simple component to display a label-value pair.
   * @param {object} props The component props.
   * @param {string} props.label The label for the detail item.
   * @param {ReactNode} props.value The value for the detail item.
   * @returns {JSX.Element}
   */
  const DetailItem = ({
    label,
    value,
  }: {
    label: string;
    value: ReactNode;
  }) => (
    <div className="grid grid-cols-3 gap-4 py-2 border-b border-slate-100 dark:border-slate-700 last:border-b-0">
      <dt className="text-sm font-medium text-gray-500 dark:text-gray-400 col-span-1">
        {label}
      </dt>
      <dd className="text-sm text-gray-900 dark:text-gray-100 col-span-2">
        {value || "-"}
      </dd>
    </div>
  );

  return (
    <div className="container mx-auto py-10 px-4 md:px-0">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Gerenciar Solicitações Beta</h1>
        <Button
          onClick={handleRefresh}
          variant="outline"
          disabled={isRefetching || isLoading} // Disable if initial loading or refetching
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${isRefetching ? "animate-spin" : ""}`}
          />
          {isRefetching ? "Atualizando..." : "Atualizar Lista"}
        </Button>
      </div>

      {/* Show toast notification for refetch errors, doesn't block UI like initial error */}
      {isError &&
        isRefetching &&
        toast.error("Erro ao atualizar", {
          description:
            (error as Error)?.message || "Não foi possível atualizar a lista.",
        })}

      {dataToDisplay.length > 0 ? (
        <BetaRequestsDataTable columns={memoizedColumns} data={dataToDisplay} />
      ) : (
        <p className="text-muted-foreground py-10 text-center">
          {isLoading ? "Carregando..." : "Nenhuma solicitação beta encontrada."}
        </p>
      )}

      {/* Details Dialog Component */}
      <Dialog open={isDetailModalOpen} onOpenChange={setIsDetailModalOpen}>
        <DialogContent className="sm:max-w-lg md:max-w-2xl">
          {/* Adjust width as needed */}
          <DialogHeader>
            <DialogTitle>Detalhes da Solicitação Beta</DialogTitle>
            <DialogDescription>
              Informações completas da solicitação de{" "}
              {selectedRequest?.contact_name || selectedRequest?.email}.
            </DialogDescription>
          </DialogHeader>
          {selectedRequest && (
            <ScrollArea className="max-h-[60vh] pr-2">
              {/* For long content */}
              <div className="space-y-1 py-4">
                <DetailItem label="Email" value={selectedRequest.email} />
                <DetailItem
                  label="Nome Contato"
                  value={selectedRequest.contact_name}
                />
                <DetailItem
                  label="Empresa"
                  value={selectedRequest.company_name}
                />
                <DetailItem
                  label="Website"
                  value={
                    selectedRequest.company_website ? (
                      <a
                        href={String(selectedRequest.company_website)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {String(selectedRequest.company_website)}
                      </a>
                    ) : (
                      "-"
                    )
                  }
                />
                <DetailItem
                  label="Status"
                  value={
                    <Badge
                      variant={getStatusBadgeVariant(selectedRequest.status)}
                      className="capitalize flex items-center w-fit"
                    >
                      {getStatusIcon(selectedRequest.status)}
                      {selectedRequest.status.replace("_", " ")}
                    </Badge>
                  }
                />
                <DetailItem
                  label="Solicitado em"
                  value={
                    selectedRequest.requested_at
                      ? format(
                          new Date(selectedRequest.requested_at),
                          "dd/MM/yyyy HH:mm",
                          { locale: ptBR }
                        )
                      : "-"
                  }
                />
                {selectedRequest.approved_at && (
                  <DetailItem
                    label="Aprovado em"
                    value={format(
                      new Date(selectedRequest.approved_at),
                      "dd/MM/yyyy HH:mm",
                      { locale: ptBR }
                    )}
                  />
                )}

                <h3 className="text-md font-semibold pt-4 pb-1 text-gray-700 dark:text-gray-300">
                  Detalhes do Negócio
                </h3>
                <DetailItem
                  label="Descrição"
                  value={
                    <p className="whitespace-pre-wrap">
                      {selectedRequest.business_description}
                    </p>
                  }
                />
                <DetailItem
                  label="Objetivo com o Beta"
                  value={
                    <p className="whitespace-pre-wrap">
                      {selectedRequest.beta_goal}
                    </p>
                  }
                />

                <h3 className="text-md font-semibold pt-4 pb-1 text-gray-700 dark:text-gray-300">
                  Informações Adicionais
                </h3>
                <DetailItem
                  label="Possui Time de Vendas?"
                  value={
                    selectedRequest.has_sales_team
                      ? "Sim"
                      : selectedRequest.has_sales_team === false
                      ? "Não"
                      : "-"
                  }
                />
                {selectedRequest.has_sales_team && (
                  <DetailItem
                    label="Tamanho do Time"
                    value={selectedRequest.sales_team_size}
                  />
                )}
                <DetailItem
                  label="Volume de Leads"
                  value={selectedRequest.avg_leads_per_period}
                />
                <DetailItem
                  label="Uso Atual do WhatsApp"
                  value={selectedRequest.current_whatsapp_usage}
                />
                <DetailItem
                  label="Disposto a dar Feedback?"
                  value={
                    selectedRequest.willing_to_give_feedback
                      ? "Sim"
                      : selectedRequest.willing_to_give_feedback === false
                      ? "Não"
                      : "-"
                  }
                />

                {selectedRequest.notes_by_admin && (
                  <>
                    <h3 className="text-md font-semibold pt-4 pb-1 text-gray-700 dark:text-gray-300">
                      Notas Internas
                    </h3>
                    <DetailItem
                      label="Notas do Admin"
                      value={
                        <p className="whitespace-pre-wrap">
                          {selectedRequest.notes_by_admin}
                        </p>
                      }
                    />
                  </>
                )}
              </div>
            </ScrollArea>
          )}
          <DialogFooter className="sm:justify-start pt-4">
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Fechar
              </Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
