// src/components/inbox/inbox-list.tsx
/**
 * @fileoverview Component to fetch and display a list of user inboxes.
 * Handles loading, error, and empty states. Provides actions to add,
 * configure, and delete inboxes.
 */
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch'; // Assuming this hook handles auth tokens
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Terminal, PlusCircle } from "lucide-react";
import { InboxItem } from './inbox-item'; // Import the item component

/**
 * Represents the structure of an Inbox object received from the API.
 */
interface Inbox {
    id: string; // UUID
    name: string;
    channel_type: string; // e.g., 'whatsapp'
    // Add other relevant fields from API if needed for display later
    // channel_details?: Record<string, any>;
    // created_at?: string;
    // updated_at?: string;
}

/**
 * Renders a list of inboxes associated with the authenticated user's account.
 * Fetches data from the '/api/v1/inboxes' endpoint.
 *
 * @component
 * @example
 * return <InboxList />
 */
export function InboxList() {
    // Custom hook to make authenticated API calls
    const authenticatedFetch = useAuthenticatedFetch();
    // State for storing the list of inboxes
    const [inboxes, setInboxes] = useState<Inbox[]>([]);
    // State to track loading status during fetch
    const [isLoading, setIsLoading] = useState<boolean>(true);
    // State to store any error message during fetch
    const [error, setError] = useState<string | null>(null);

    /**
     * Placeholder function to trigger the display of the 'Create Inbox' modal or form.
     * TODO: Implement modal display logic.
     */
    const handleOpenCreateModal = useCallback(() => {
        console.log("TODO: Open Create Inbox Modal");
        // Example: setCreateModalOpen(true);
    }, []); // No dependencies needed if it just sets local state

    /**
     * Placeholder function to navigate to the configuration page for a specific inbox.
     * @param {string} inboxId - The ID of the inbox to configure.
     * TODO: Implement navigation logic (e.g., using Next.js router).
     */
    const handleConfigureInbox = useCallback((inboxId: string) => {
        console.log("TODO: Navigate to configure inbox:", inboxId);
        // Example: router.push(`/dashboard/inboxes/${inboxId}/settings`);
    }, []); // No dependencies needed if it just navigates

    /**
     * Placeholder function to initiate the deletion process for an inbox.
     * @param {string} inboxId - The ID of the inbox to delete.
     * TODO: Implement confirmation modal and API call for deletion.
     */
    const handleDeleteInbox = useCallback((inboxId: string) => {
        console.log("TODO: Show delete confirmation for inbox:", inboxId);
        // Example: setConfirmDelete({ open: true, inboxId });
    }, []); // No dependencies needed if it just sets local state

    /**
     * Fetches the list of inboxes from the backend API.
     * Wrapped in useCallback to memoize the function, dependent on `authenticatedFetch`.
     */
    const fetchInboxes = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        console.log("[InboxList] Fetching inboxes..."); // Keep for debugging during dev
        try {
            const response = await authenticatedFetch('/api/v1/inboxes');

            if (!response.ok) {
                let errorDetail = `Error: ${response.status} ${response.statusText}`;
                try {
                    // Attempt to parse backend error detail if available
                    const errorData = await response.json();
                    errorDetail = errorData.detail || errorDetail;
                } catch (e) {
                    // Ignore if response body is not JSON or empty
                }
                throw new Error(errorDetail);
            }

            const data: Inbox[] = await response.json();
            console.log("[InboxList] Inboxes received:", data); // Keep for debugging during dev
            setInboxes(data);

        } catch (err: unknown) { // Use 'unknown' for better type safety
            console.error("[InboxList] Fetch Error:", err);
            let message = 'An unknown error occurred while fetching inboxes.';
            if (err instanceof Error) {
                // Use the message from the Error object if available
                message = err.message;
            }
            setError(message);
            setInboxes([]); // Clear inboxes on error
        } finally {
            setIsLoading(false);
        }
    }, [authenticatedFetch]); // Dependency: Re-run if the fetch function instance changes

    // Effect hook to fetch inboxes when the component mounts or fetchInboxes changes.
    useEffect(() => {
        fetchInboxes();
    }, [fetchInboxes]); // Dependency: Ensures fetch runs on mount and if fetchInboxes changes

    // --- Render Logic ---

    return (
        <div className="space-y-4 p-4 md:p-6"> {/* Added responsive padding */}
            {/* Header Section */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-4">
                 <h2 className="text-xl font-semibold tracking-tight">Your Inboxes</h2>
                 <Button size="sm" onClick={handleOpenCreateModal} disabled={isLoading}>
                     <PlusCircle className="mr-2 h-4 w-4" /> Add Inbox
                 </Button>
             </div>

             {/* Content Section: Loading, Error, Empty, or List */}
             {isLoading ? (
                 // Skeleton Loader View
                 <div className="space-y-3">
                    <Skeleton className="h-16 w-full rounded-lg" />
                    <Skeleton className="h-16 w-full rounded-lg" />
                    <Skeleton className="h-16 w-full rounded-lg" />
                 </div>
             ) : error ? (
                 // Error Display View
                 <Alert variant="destructive">
                    <Terminal className="h-4 w-4" />
                    <AlertTitle>Failed to Load Inboxes</AlertTitle>
                    <AlertDescription>
                        {error}
                        <Button variant="link" size="sm" onClick={fetchInboxes} className="ml-2 p-0 h-auto">
                            Try again
                        </Button>
                    </AlertDescription>
                 </Alert>
             ) : inboxes.length === 0 ? (
                 // Empty State View
                 <button
                    onClick={handleOpenCreateModal} // Trigger create action
                    className="flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-border p-8 text-center hover:border-primary/50 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 transition-colors"
                    aria-label="Add your first inbox"
                 >
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mb-4">
                         <PlusCircle className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <h3 className="text-lg font-medium">No Inboxes Yet</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Get started by creating your first inbox channel.
                    </p>
                 </button>
             ) : (
                 // Inboxes List View
                 <div className="space-y-3">
                    {inboxes.map((inbox) => (
                        <InboxItem
                            key={inbox.id} // React key for list rendering
                            inbox={inbox}
                            onConfigureClick={handleConfigureInbox} // Pass handler
                            onDeleteClick={handleDeleteInbox}     // Pass handler
                        />
                    ))}
                 </div>
             )}
        </div>
    );
}