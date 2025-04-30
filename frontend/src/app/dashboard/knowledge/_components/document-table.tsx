// src/components/dashboard/knowledge/DocumentTable.tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { format } from "date-fns"; // For date formatting
import { Loader2, Trash2 } from "lucide-react"; // Icons

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { components } from "@/types/api"; // API type definitions

// Define types based on your API schema
type KnowledgeDocumentRead = components["schemas"]["KnowledgeDocumentRead"];
// Ensure this matches the possible status strings from your backend exactly
type DocumentStatus = KnowledgeDocumentRead["status"]; // More robust typing

interface DocumentTableProps {
  /** Array of knowledge documents to display. */
  documents: KnowledgeDocumentRead[];
  /** Callback function triggered when the delete action is confirmed. */
  onDelete: (documentId: string) => void;
  /** The ID of the document currently being deleted, or null. Used for visual feedback. */
  isDeletingId: string | null;
  /** Optional: Indicates if the table data is currently being refreshed (e.g., polling). */
  isPolling?: boolean;
}

/**
 * Maps document processing status to corresponding Badge variants for styling.
 * @param {DocumentStatus} status - The current status of the document.
 * @returns {"default" | "secondary" | "destructive" | "outline"} The Shadcn Badge variant.
 */
const getStatusVariant = (
  status: DocumentStatus
): "default" | "secondary" | "destructive" | "outline" => {
  switch (
    status?.toUpperCase() // Use uppercase for case-insensitive matching
  ) {
    case "COMPLETED":
      return "default"; // Or use a specific 'success' variant if defined in your theme
    case "PROCESSING":
      return "secondary";
    case "PENDING":
      return "outline";
    case "FAILED":
      return "destructive";
    default:
      return "secondary"; // Fallback for unknown statuses
  }
};

/**
 * Renders a table displaying knowledge base documents with status and actions.
 * Includes pagination controls and confirmation dialog for deletion.
 * @param {DocumentTableProps} props - The component props.
 */
export function DocumentTable({
  documents,
  onDelete,
  isDeletingId,
  isPolling, // Destructure isPolling
}: DocumentTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {/* User-facing text translated to pt-BR */}
          <TableHead className="w-[35%]">Fonte</TableHead>
          <TableHead>Tipo</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Chunks</TableHead>
          <TableHead>Adicionado em</TableHead>
          <TableHead className="text-right">Ações</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((doc) => (
          <TableRow key={doc.id} className={isPolling ? "opacity-75" : ""}>
            {" "}
            {/* Subtle indication during polling */}
            <TableCell
              className="font-medium truncate max-w-xs"
              title={
                (doc.source_type === "file"
                  ? doc.original_filename
                  : doc.source_uri) ?? undefined
              }
            >
              {/* Display filename for files, URI for others */}
              {doc.source_type === "file"
                ? doc.original_filename
                : doc.source_uri}
            </TableCell>
            <TableCell className="capitalize">{doc.source_type}</TableCell>
            <TableCell>
              <Badge
                variant={getStatusVariant(doc.status)}
                className="capitalize"
              >
                {doc.status?.toLowerCase() ?? "desconhecido"}{" "}
                {/* Display status consistently */}
              </Badge>
              {/* Show truncated error message if status is 'failed' */}
              {doc.status?.toUpperCase() === "FAILED" && doc.error_message && (
                <p
                  className="text-xs text-destructive mt-1"
                  title={doc.error_message} // Full error on hover
                >
                  Erro: {doc.error_message.substring(0, 50)}
                  {doc.error_message.length > 50 ? "..." : ""}
                </p>
              )}
            </TableCell>
            <TableCell>{doc.chunk_count ?? "-"}</TableCell>
            <TableCell>
              {/* Format date, handle potential invalid date string */}
              {doc.created_at
                ? format(new Date(doc.created_at), "dd/MM/yyyy")
                : "-"}
            </TableCell>
            <TableCell className="text-right">
              {/* Delete Confirmation Dialog */}
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={isDeletingId === doc.id} // Disable button if this specific item is being deleted
                    aria-label={`Excluir documento ${
                      doc.original_filename || doc.source_uri
                    }`} // pt-BR
                  >
                    {isDeletingId === doc.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4 text-destructive" />
                    )}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    {/* User-facing text translated to pt-BR */}
                    <AlertDialogTitle>
                      Você tem certeza absoluta?
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      Essa ação não pode ser desfeita. Isso excluirá
                      permanentemente a fonte do documento{" "}
                      <span className="font-medium break-all">
                        &quot;{doc.original_filename || doc.source_uri}&quot;
                      </span>{" "}
                      e todos os seus chunks de conhecimento associados do banco
                      de dados.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    {/* User-facing text translated to pt-BR */}
                    <AlertDialogCancel>Cancelar</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => onDelete(doc.id)} // Call onDelete only when confirmed
                      className="bg-destructive hover:bg-destructive/90"
                    >
                      Continuar
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
