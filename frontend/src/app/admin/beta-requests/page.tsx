// src/app/admin/beta-requests/page.tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog, // Para o botão de fechar
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"; // Importar componentes do Dialog
import { ScrollArea } from "@/components/ui/scroll-area";
import { useLayoutContext } from "@/contexts/layout-context";
import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";
import { components } from "@/types/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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

// Chave da query para a lista de solicitações beta
const ADMIN_BETA_REQUESTS_QUERY_KEY = "adminBetaRequests";

export default function AdminBetaRequestsPage() {
  const { setPageTitle } = useLayoutContext();
  const fetcher = useAuthenticatedFetch();
  const queryClient = useQueryClient();

  // Estados para rastrear qual item está sendo aprovado/negado para feedback na UI
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
    queryKey: [ADMIN_BETA_REQUESTS_QUERY_KEY], // Adicionar filtros/paginações aqui se a API suportar e você quiser que a chave reflita isso
    queryFn: async () => {
      if (!fetcher) throw new Error("Fetcher não disponível");
      // TODO: Adicionar parâmetros de paginação e filtro à chamada da API
      const response = await fetcher(
        "/api/v1/admin/beta/requests?page=1&size=50"
      ); // Exemplo inicial
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail ||
            `Falha ao buscar solicitações: ${response.statusText}`
        );
      }
      return response.json();
    },
    enabled: !!fetcher,
  });

  const approveMutation = useMutation<AdminBetaActionResponse, Error, string>({
    mutationFn: (email: string) => {
      if (!fetcher) throw new Error("Fetcher não disponível");
      setProcessingAction({ email, type: "approve" });
      return fetcher(`/api/v1/admin/beta/requests/${email}/approve`, {
        method: "POST",
      }).then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha ao aprovar.");
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
      setProcessingAction(null);
    },
  });

  const denyMutation = useMutation<AdminBetaActionResponse, Error, string>({
    mutationFn: (email: string) => {
      if (!fetcher) throw new Error("Fetcher não disponível");
      setProcessingAction({ email, type: "deny" });
      return fetcher(`/api/v1/admin/beta/requests/${email}/deny`, {
        method: "POST",
      }).then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Falha ao negar.");
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
      setProcessingAction(null);
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
  // Memoize as colunas para evitar recriação desnecessária
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
    [processingAction, handleApprove, handleDeny, handleViewDetails]
  ); // Recriar colunas se processingAction mudar para atualizar o estado disabled/loading dos botões

  const handleRefresh = () => {
    toast.info("Atualizando lista de solicitações...");
    refetch(); // Chama a função refetch do useQuery
  };

  if (isLoading && !isRefetching) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="ml-4">Carregando solicitações beta...</p>
      </div>
    );
  }

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
  const DetailItem = ({
    label,
    value,
  }: {
    label: string;
    value: ReactNode;
  }) => (
    <div className="grid grid-cols-3 gap-4 py-2 border-b border-slate-100 last:border-b-0">
      <dt className="text-sm font-medium text-gray-500 col-span-1">{label}</dt>
      <dd className="text-sm text-gray-900 col-span-2">{value || "-"}</dd>
    </div>
  );

  return (
    <div className="container mx-auto py-10 px-4 md:px-0">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Gerenciar Solicitações Beta</h1>
        <Button
          onClick={handleRefresh}
          variant="outline"
          disabled={isRefetching || isLoading}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${isRefetching ? "animate-spin" : ""}`}
          />
          {isRefetching ? "Atualizando..." : "Atualizar Lista"}
        </Button>
      </div>

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

      {/* --- INÍCIO: Componente Dialog para Detalhes --- */}
      <Dialog open={isDetailModalOpen} onOpenChange={setIsDetailModalOpen}>
        <DialogContent className="sm:max-w-lg md:max-w-2xl">
          {" "}
          {/* Ajuste o tamanho conforme necessário */}
          <DialogHeader>
            <DialogTitle>Detalhes da Solicitação Beta</DialogTitle>
            <DialogDescription>
              Informações completas da solicitação de{" "}
              {selectedRequest?.contact_name || selectedRequest?.email}.
            </DialogDescription>
          </DialogHeader>
          {selectedRequest && (
            <ScrollArea className="max-h-[60vh] pr-2">
              {" "}
              {/* Para conteúdo longo */}
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

                <h3 className="text-md font-semibold pt-4 pb-1 text-gray-700">
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

                <h3 className="text-md font-semibold pt-4 pb-1 text-gray-700">
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
                    <h3 className="text-md font-semibold pt-4 pb-1 text-gray-700">
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
      {/* --- FIM: Componente Dialog para Detalhes --- */}
    </div>
  );
}
