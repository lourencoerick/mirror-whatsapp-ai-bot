// src/app/admin/beta-requests/columns.tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AppBetaStatusEnum } from "@/lib/enums"; // Seu enum do frontend
import { components } from "@/types/api"; // Seus tipos OpenAPI
import { ColumnDef } from "@tanstack/react-table";
import {
  format, // Para formatar datas
} from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  ArrowUpDown,
  CheckCircle,
  Eye,
  Hourglass,
  MoreHorizontal,
  XCircle,
} from "lucide-react";

// Tipo para os dados da linha, baseado no seu schema AdminBetaTesterRead
export type BetaRequestRow = components["schemas"]["AdminBetaTesterRead"];

// Função para obter o estilo do badge de status
export const getStatusBadgeVariant = (
  status: BetaRequestRow["status"]
): "default" | "secondary" | "destructive" | "outline" => {
  switch (status) {
    case AppBetaStatusEnum.APPROVED:
      return "default"; // Verde (shadcn default é geralmente primário)
    case AppBetaStatusEnum.PENDING_APPROVAL:
      return "secondary"; // Amarelo/Cinza
    case AppBetaStatusEnum.DENIED:
      return "destructive"; // Vermelho
    default:
      return "outline";
  }
};
export const getStatusIcon = (status: BetaRequestRow["status"]) => {
  switch (status) {
    case AppBetaStatusEnum.APPROVED:
      return <CheckCircle className="mr-2 h-4 w-4 text-green-500" />;
    case AppBetaStatusEnum.PENDING_APPROVAL:
      return <Hourglass className="mr-2 h-4 w-4 text-yellow-500" />;
    case AppBetaStatusEnum.DENIED:
      return <XCircle className="mr-2 h-4 w-4 text-red-500" />;
    default:
      return null;
  }
};

// Definição das colunas
export const columns = (
  onApprove: (email: string) => void,
  onDeny: (email: string) => void,
  onViewDetails: (request: BetaRequestRow) => void,
  isApproving: (email: string) => boolean,
  isDenying: (email: string) => boolean
): ColumnDef<BetaRequestRow>[] => [
  {
    accessorKey: "email",
    header: ({ column }) => (
      <Button
        variant="ghost"
        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
      >
        Email <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: ({ row }) => (
      <div className="font-medium">{row.getValue("email")}</div>
    ),
  },
  {
    accessorKey: "contact_name",
    header: "Nome do Contato",
    cell: ({ row }) => row.getValue("contact_name") || "-",
  },
  {
    accessorKey: "company_name",
    header: "Empresa",
    cell: ({ row }) => row.getValue("company_name") || "-",
  },
  {
    accessorKey: "requested_at",
    header: ({ column }) => (
      <Button
        variant="ghost"
        onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
      >
        Solicitado em <ArrowUpDown className="ml-2 h-4 w-4" />
      </Button>
    ),
    cell: ({ row }) => {
      const date = row.getValue("requested_at");
      return date
        ? format(new Date(date as string), "dd/MM/yyyy HH:mm", { locale: ptBR })
        : "-";
    },
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as BetaRequestRow["status"];
      return (
        <Badge variant={getStatusBadgeVariant(status)} className="capitalize">
          {getStatusIcon(status)}
          {status.replace("_", " ")}
        </Badge>
      );
    },
    filterFn: (row, id, value) => {
      // Para filtro por select
      return value.includes(row.getValue(id));
    },
  },
  {
    id: "actions",
    cell: ({ row }) => {
      const request = row.original;
      const email = request.email;

      return (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-8 w-8 p-0">
              <span className="sr-only">Abrir menu</span>
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Ações</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => onViewDetails(request)}>
              {" "}
              {/* <<< CHAMAR onViewDetails */}
              <Eye className="mr-2 h-4 w-4" /> Ver Detalhes
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => navigator.clipboard.writeText(email)}
            >
              Copiar Email
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {/* Lógica de Aprovar/Negar como antes */}
            {request.status === AppBetaStatusEnum.PENDING_APPROVAL && (
              <>
                <DropdownMenuItem
                  onClick={() => onApprove(email)}
                  disabled={isApproving(email) || isDenying(email)}
                  className="text-green-600 hover:!text-green-700"
                >
                  {isApproving(email) ? "Aprovando..." : "Aprovar"}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => onDeny(email)}
                  disabled={isApproving(email) || isDenying(email)}
                  className="text-red-600 hover:!text-red-700"
                >
                  {isDenying(email) ? "Negando..." : "Negar"}
                </DropdownMenuItem>
              </>
            )}
            {/* ... (outras ações condicionais como antes) ... */}
            {request.status === AppBetaStatusEnum.APPROVED && (
              <DropdownMenuItem
                onClick={() => onDeny(email)}
                disabled={isDenying(email)}
                className="text-red-600 hover:!text-red-700"
              >
                {isDenying(email) ? "Negando..." : "Mover para Negado"}
              </DropdownMenuItem>
            )}
            {request.status === AppBetaStatusEnum.DENIED && (
              <DropdownMenuItem
                onClick={() => onApprove(email)}
                disabled={isApproving(email)}
                className="text-green-600 hover:!text-green-700"
              >
                {isApproving(email) ? "Aprovando..." : "Mover para Aprovado"}
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      );
    },
  },
];
