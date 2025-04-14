
/** * @fileoverview Component to fetch and display a list of user inboxes.
 * Handles loading, error, and empty states. Provides actions to add,
 * configure, and delete inboxes.
 */
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation'; 
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch';
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Terminal, PlusCircle, Loader2 } from "lucide-react"; 
import { InboxItem } from './inbox-item';
import { Inbox } from "@/types/inbox";
import * as inboxService from '@/lib/api/inbox';
import { toast } from "sonner"; 
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

/**
 * State for managing the delete confirmation dialog.
 */
interface DeleteConfirmState {
    isOpen: boolean;
    inboxId: string | null;
    inboxName: string | null;
    isDeleting: boolean; 
}

/**
 * Renders a list of inboxes associated with the authenticated user's account.
 */
export function InboxList() {
    const router = useRouter(); 
    const authenticatedFetch = useAuthenticatedFetch();
    const [inboxes, setInboxes] = useState<Inbox[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [deleteConfirm, setDeleteConfirm] = useState<DeleteConfirmState>({
        isOpen: false,
        inboxId: null,
        inboxName: null,
        isDeleting: false,
    });

    // --- Fetch Logic (Keeps existing fetchAndSetInboxes) ---
    const fetchAndSetInboxes = useCallback(async (showLoading = true) => {
        if (showLoading) setIsLoading(true);
        setError(null);
        console.log("[InboxList] Fetching inboxes via service...");
        try {
            const data = await inboxService.fetchInboxes(authenticatedFetch);
            console.log("[InboxList] Inboxes received via service:", data);
            setInboxes(data);
        } catch (err: unknown) {
            console.error("[InboxList] Fetch error:", err);
            let message = 'An unknown error occurred while fetching inboxes.';
            if (err instanceof Error) {
                message = err.message;
            }
            setError(message);
            setInboxes([]);
        } finally {
            if (showLoading) setIsLoading(false);
        }
    }, [authenticatedFetch]);

    useEffect(() => {
        fetchAndSetInboxes();
    }, [fetchAndSetInboxes]);

    // --- Action Handlers ---
    const handleOpenCreateModal = useCallback(() => {
        router.push('/dashboard/inboxes/create');
    }, [router]);

    /**
     * Navigates to the settings page for a specific inbox.
     * @param {string} inboxId - The ID of the inbox to configure.
     */
    const handleConfigureInbox = useCallback((inboxId: string) => {
        console.log("Navigating to configure inbox:", inboxId);
        router.push(`/dashboard/inboxes/${inboxId}/settings`);
    }, [router]);

    /**
     * Opens the delete confirmation dialog for the specified inbox.
     * @param {string} inboxId - The ID of the inbox to potentially delete.
     */
    const handleOpenDeleteConfirm = useCallback((inboxId: string) => {
        const inboxToDelete = inboxes.find(inbox => inbox.id === inboxId);
        if (inboxToDelete) {
            setDeleteConfirm({
                isOpen: true,
                inboxId: inboxId,
                inboxName: inboxToDelete.name,
                isDeleting: false,
            });
        } else {
            console.warn("Attempted to delete an inbox not found in the current list:", inboxId);
            toast.error("Não foi possível encontrar a caixa de entrada para excluir.");
        }
    }, [inboxes]);

    /**
     * Closes the delete confirmation dialog.
     */
    const handleCloseDeleteConfirm = useCallback(() => {
        if (deleteConfirm.isDeleting) return; 
        setDeleteConfirm({ isOpen: false, inboxId: null, inboxName: null, isDeleting: false });
    }, [deleteConfirm.isDeleting]);

    /**
     * Performs the deletion process after confirmation.
     */
    const handleConfirmDelete = useCallback(async () => {
        if (!deleteConfirm.inboxId || deleteConfirm.isDeleting) return;

        setDeleteConfirm(prev => ({ ...prev, isDeleting: true }));
        const toastId = toast.loading(`Excluindo a caixa de entrada "${deleteConfirm.inboxName}"...`);

        try {
            await inboxService.deleteInbox(deleteConfirm.inboxId, authenticatedFetch);
            toast.success(`Caixa de entrada "${deleteConfirm.inboxName}" excluída com sucesso.`, { id: toastId });
            setDeleteConfirm({ isOpen: false, inboxId: null, inboxName: null, isDeleting: false });
            await fetchAndSetInboxes(false);

        } catch (err: unknown) {
            console.error("Delete error:", err);
            const message = err instanceof Error ? err.message : "An unknown error occurred.";
            toast.error(`Falha ao excluir a caixa de entrada: ${message}`, { id: toastId });
            setDeleteConfirm(prev => ({ ...prev, isDeleting: false }));
        }
    }, [deleteConfirm, authenticatedFetch, fetchAndSetInboxes]);

    // --- Render Logic ---
    return (
        <> {/* Fragment to wrap list and dialog */}
            <div className="space-y-4 p-4 md:p-6">
                {/* Header section (button now navigates) */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-4">
                    <h2 className="text-xl font-semibold tracking-tight">Minhas Caixas de Entrada</h2>
                    <Button size="sm" onClick={handleOpenCreateModal} disabled={isLoading}>
                        <PlusCircle className="mr-2 h-4 w-4" /> Adicionar Caixa de Entrada
                    </Button>
                </div>

                {/* Content section: Loading, Error, Empty, or List */}
                {isLoading ? (
                    <div className="space-y-3">
                        <Skeleton className="h-16 w-full rounded-lg" />
                        <Skeleton className="h-16 w-full rounded-lg" />
                        <Skeleton className="h-16 w-full rounded-lg" />
                    </div>
                ) : error ? (
                    <Alert variant="destructive">
                        <Terminal className="h-4 w-4" />
                        <AlertTitle>Falha ao Carregar as Caixas de Entrada</AlertTitle>
                        <AlertDescription>
                            {error}
                            <Button variant="link" size="sm" onClick={() => fetchAndSetInboxes(true)} className="ml-2 p-0 h-auto">
                                Tentar novamente
                            </Button>
                        </AlertDescription>
                    </Alert>
                ) : inboxes.length === 0 ? (
                    <button
                        onClick={handleOpenCreateModal} // Triggers creation
                        className="flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-border p-8 text-center hover:border-primary/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-colors"
                        aria-label="Adicione sua primeira caixa de entrada"
                    >
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mb-4">
                            <PlusCircle className="h-6 w-6 text-muted-foreground" />
                        </div>
                        <h3 className="text-lg font-medium">Ainda não há caixas de entrada</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Comece criando seu primeiro canal de caixa de entrada.
                        </p>
                    </button>
                ) : (
                    <div className="space-y-3">
                        {inboxes.map((inbox) => (
                            <InboxItem
                                key={inbox.id}
                                inbox={inbox}
                                onConfigureClick={handleConfigureInbox}
                                onDeleteClick={handleOpenDeleteConfirm}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Delete Confirmation Dialog */}
            <AlertDialog open={deleteConfirm.isOpen} onOpenChange={(open) => !open && handleCloseDeleteConfirm()}>
                {/* <AlertDialogTrigger> - We trigger manually via state */}
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Você tem certeza absoluta?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Esta ação não pode ser desfeita. Isso excluirá permanentemente a caixa de entrada
                            <strong className="mx-1">{deleteConfirm.inboxName ?? '...'}</strong>
                            e todos os dados associados (conversas, mensagens, etc...).
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel onClick={handleCloseDeleteConfirm} disabled={deleteConfirm.isDeleting}>
                            Cancelar
                        </AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleConfirmDelete}
                            disabled={deleteConfirm.isDeleting}
                            className="bg-destructive hover:bg-destructive/90"
                        >
                            {deleteConfirm.isDeleting ? (
                                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Excluindo...</>
                            ) : (
                                "Sim, excluir a caixa de entrada"
                            )}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}
