'use client';

import React, { useState, useCallback, useEffect } from 'react';
import useSWR from 'swr';
import { toast } from "sonner";
import Link from 'next/link'; // Import Link for navigation
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button"; // Import Button
import { PaginatedContact, Contact } from '@/types/contact';
import ContactSearchBar from '@/components/ui/contact/contact-search-bar';
import ContactList from '@/components/ui/contact/contact-list';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch';
import { useLayoutContext } from '@/contexts/layout-context';
import { AddContactDialog } from '@/components/ui/contact/add-contact-dialog';
import { EditContactDialog } from '@/components/ui/contact/edit-contact-dialog';
import { Loader2, UploadCloud } from 'lucide-react'; // Import Loader2 and UploadCloud icon

// --- Constants ---
const ITEMS_PER_PAGE = 10;

/**
 * Main page component for displaying and managing contacts with search, sort, and pagination.
 * Texts are in Brazilian Portuguese.
 */
export default function ContactsPage() {
  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle("Contatos");
  }, [setPageTitle]);

  // --- Component States ---
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortBy, setSortBy] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [contactToEdit, setContactToEdit] = useState<Contact | null>(null);
  const [contactToDelete, setContactToDelete] = useState<{ id: string; name: string | null } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const authenticatedFetch = useAuthenticatedFetch();

  // --- SWR Fetcher ---
  const fetcher = useCallback(async (url: string): Promise<PaginatedContact> => {
    const res = await authenticatedFetch(url);
    if (!res.ok) {
      const errorInfo = await res.json().catch(() => ({}));
      throw new Error(errorInfo.detail || `An error occurred: ${res.statusText} (${res.status})`);
    }
    return res.json();
  }, [authenticatedFetch]);

  // --- API URL Construction ---
  const apiUrl = React.useMemo(() => {
    const offset = (currentPage - 1) * ITEMS_PER_PAGE;
    let url = `/api/v1/contacts?limit=${ITEMS_PER_PAGE}&offset=${offset}`;
    if (searchTerm) {
      url += `&search=${encodeURIComponent(searchTerm)}`;
    }
    if (sortBy) {
      url += `&sort_by=${sortBy}&sort_direction=${sortDirection}`;
    }
    return url;
  }, [currentPage, searchTerm, sortBy, sortDirection]);

  // --- Data Fetching with SWR ---
  const { data: paginatedData, error, isLoading, mutate } = useSWR<PaginatedContact, Error>(
    apiUrl,
    fetcher,
    { keepPreviousData: true }
  );

  // Calculate total pages
  const totalPages = paginatedData ? Math.ceil(paginatedData.total / ITEMS_PER_PAGE) : 0;

  // --- Event Handlers ---
  const handleSearchChange = useCallback((term: string) => {
    setSearchTerm(term);
    setCurrentPage(1);
  }, []);

  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  const handleSortChange = useCallback((newSortBy: string) => {
    if (newSortBy === sortBy) {
      setSortDirection(prevDir => (prevDir === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(newSortBy);
      setSortDirection('asc');
    }
    setCurrentPage(1);
  }, [sortBy]);

  // --- Edit Action Handlers ---
  const handleEditContact = useCallback((contactId: string) => {
    const contact = paginatedData?.items.find(c => c.id.toString() === contactId);
    if (contact) {
      setContactToEdit(contact);
    } else {
      console.warn("Contact not found in current data for editing:", contactId);
      toast.error("Contato não encontrado para edição.");
    }
  }, [paginatedData?.items]);

  const handleCloseEditDialog = () => {
    setContactToEdit(null);
  };

  // --- Delete Action Handlers ---
  const handleDeleteContact = (contactId: string) => {
    const contact = paginatedData?.items.find(c => c.id.toString() === contactId);
    setContactToDelete({
        id: contactId,
        name: contact?.name || contactId
    });
  };

  const confirmDeleteContact = async () => {
    if (!contactToDelete) return;
    setIsDeleting(true);
    try {
      const response = await authenticatedFetch(`/api/v1/contacts/${contactToDelete.id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errorInfo = await response.json().catch(() => ({}));
        throw new Error(errorInfo.detail || `Falha ao excluir contato: ${response.statusText}`);
      }
      mutate();
      toast.success(`Contato "${contactToDelete.name || contactToDelete.id}" excluído com sucesso!`);
      setContactToDelete(null);
    } catch (err: any) {
      console.error("Error deleting contact:", err);
      toast.error(`Erro ao excluir contato: ${err.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const cancelDeleteContact = () => {
    setContactToDelete(null);
  };

  // --- Render Logic ---

  if (error) {
    return (
      <div className="container mx-auto p-4 text-center text-red-600">
        <p>Falha ao carregar contatos:</p>
        <p>{error.message || "Ocorreu um erro desconhecido."}</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
      {/* Top Bar: Search and Action Buttons */}
      <div className="flex flex-col sm:flex-row justify-between items-center mb-4 gap-4">
        {/* Search Bar */}
        <div className="w-full sm:w-auto flex-grow">
          <ContactSearchBar onSearchChange={handleSearchChange} placeholder="Buscar por nome, email ou telefone..." />
        </div>

        {/* Action Buttons Group */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Import Button */}
          <Link href="/dashboard/contacts/import" passHref legacyBehavior>
            <Button variant="outline" asChild>
              <a> {/* Use anchor tag inside Button with asChild */}
                <UploadCloud className="mr-2 h-4 w-4" />
                Importar em Lote
              </a>
            </Button>
          </Link>

          {/* Add Contact Dialog Trigger */}
          <AddContactDialog mutate={mutate} />
        </div>
      </div>

      {/* Contact List */}
      <ContactList
        contacts={paginatedData?.items ?? []}
        isLoading={isLoading && !paginatedData?.items}
        onEdit={handleEditContact}
        onDelete={handleDeleteContact}
        sortBy={sortBy}
        sortDirection={sortDirection}
        onSortChange={handleSortChange}
      />

      {/* Pagination Controls */}
      {paginatedData && paginatedData.total > 0 && totalPages > 1 && (
        <PaginationControls
          currentPage={currentPage}
          totalItems={paginatedData.total}
          itemsPerPage={ITEMS_PER_PAGE}
          onPageChange={handlePageChange}
          totalPages={totalPages}
          className="border-t bg-card"
        />
      )}

      {/* Edit Contact Dialog */}
      <EditContactDialog
        contact={contactToEdit}
        onClose={handleCloseEditDialog}
        mutate={mutate}
      />

      {/* Delete Confirmation Alert Dialog */}
      <AlertDialog open={!!contactToDelete} onOpenChange={(open) => !open && cancelDeleteContact()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar Exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja excluir o contato{' '}
              <strong className="font-medium">{contactToDelete?.name || contactToDelete?.id}</strong>?
              Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={cancelDeleteContact} disabled={isDeleting}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteContact} disabled={isDeleting} className="bg-destructive hover:bg-destructive/90">
              {isDeleting ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Excluindo...</>
              ) : ( 'Excluir' )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

    </div>
  );
}