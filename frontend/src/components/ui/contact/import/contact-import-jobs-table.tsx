'use client';

import React, { useState } from 'react'; 
import useSWR from 'swr';
import { format } from 'date-fns';
import { cn } from "@/lib/utils"; 


import { useAuthenticatedFetch, FetchFunction } from '@/hooks/use-authenticated-fetch'; 
import { listContactImportJobs  } from '@/lib/api/contact'; 
import { PaginatedImportJobListResponse, ImportJobListItem  } from '@/types/contact-import'; 

import JobStatusDetails from './import-job-details'; 

import {
    Table,
    TableBody,
    TableCaption,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Info } from 'lucide-react';
import { BadgeProps } from '@/components/ui/badge'
const ITEMS_PER_PAGE = 10;

/**
 * Maps job status strings to Badge variants.
 * @param {string | undefined} status - The job status string.
 * @returns { BadgeProps } The badge variant.
 */
const getStatusVariant = (status?: string): BadgeProps['variant'] => {
    switch (status?.toUpperCase()) {
        case 'COMPLETE':
            return 'success';
        case 'FAILED':
            return 'destructive';
        case 'PROCESSING':
            return 'default';
        case 'PENDING':
            return 'secondary';
        default:
            return 'outline';
    }
};

/**
 * Formats a date string or returns a placeholder.
 * @param {string | null | undefined} dateString - The ISO date string.
 * @param {string} placeholder - Text to show if date is null/undefined.
 * @returns {string} Formatted date or placeholder.
 */
const formatDate = (dateString: string | null | undefined, placeholder: string = 'N/A'): string => {
    if (!dateString) return placeholder;
    try {
        return format(new Date(dateString), 'dd/MM/yyyy HH:mm');
    } catch (error) {
        console.error("Error formatting date:", dateString, error);
        return 'Invalid Date';
    }
};

/**
 * Renders a table displaying the history of contact import jobs with pagination
 * and collapsible rows for viewing job details.
 * @component
 */
const ContactImportJobsTable: React.FC = () => {
    const [currentPage, setCurrentPage] = useState(1);
    // State to keep track of expanded rows using job ID as key
    const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
    // Get the authenticated fetch function instance
    const authenticatedFetch = useAuthenticatedFetch();

    // SWR key includes page and size to refetch on change
    const swrKey = [`/api/v1/contacts/batch/import/jobs`, currentPage, ITEMS_PER_PAGE];

    /**
     * SWR fetcher function to list import jobs.
     * @param {Array} key - SWR key array.
     * @param {AuthenticatedFetchFunction} fetchFn - Authenticated fetch instance.
     * @returns {Promise<PaginatedImportJobListResponse>} Paginated job list.
     */
    const fetcher = (
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        [_url, page, size]: [string, number, number],
        fetchFn: FetchFunction
    ): Promise<PaginatedImportJobListResponse> => {
        return listContactImportJobs(page, size, fetchFn);
    };

    // Use SWR to fetch the list of jobs
    const { data, error, isLoading } = useSWR<PaginatedImportJobListResponse>(
        swrKey,
        (key) => fetcher(key as [string, number, number], authenticatedFetch),
        {
            keepPreviousData: true, 
            revalidateOnFocus: true, 
            refreshInterval: (data) => {
                if (!data) return 5000;
    
                const hasActiveJob = data.items.some(
                    (job) => job.status === 'PROCESSING' || job.status === 'PENDING'
                );
    
                return hasActiveJob ? 5000 : 0; 
            }
        }            
    );

    /** Toggles the expanded state for a given job ID */
    const toggleRowExpansion = (jobId: string) => {
        setExpandedRows(prev => ({
            ...prev,
            [jobId]: !prev[jobId] // Toggle the boolean value for the specific job ID
        }));
    };

    /** Handles navigation to the previous page */
    const handlePreviousPage = () => {
        if (currentPage > 1) {
            setCurrentPage(prev => prev - 1);
            setExpandedRows({}); // Collapse all rows when changing page
        }
    };

    /** Handles navigation to the next page */
    const handleNextPage = () => {
        if (data && currentPage < data.total_pages) {
            setCurrentPage(prev => prev + 1);
            setExpandedRows({}); // Collapse all rows when changing page
        }
    };

    /** Renders the main body content of the table */
    const renderTableContent = () => {
        // Define the total number of columns including the new expansion button column
        const numberOfColumns = 6;

        // --- Loading State ---
        if (isLoading && !data) {
            return Array.from({ length: ITEMS_PER_PAGE }).map((_, index) => (
                <TableRow key={`skeleton-${index}`}>
                    <TableCell className="w-[50px] px-2">
                        <Skeleton className="h-8 w-8 rounded-sm" />
                    </TableCell>
                    <TableCell>
                        <Skeleton className="h-4 w-[100px]" />
                    </TableCell>
                    <TableCell>
                        <Skeleton className="h-4 w-[150px]" />
                    </TableCell>
                    <TableCell>
                        <Skeleton className="h-4 w-[80px]" />
                    </TableCell>
                    <TableCell>
                        <Skeleton className="h-4 w-[120px]" />
                    </TableCell>
                    <TableCell>
                        <Skeleton className="h-4 w-[120px]" />
                    </TableCell>
                </TableRow>
            ));
        }

        // --- Error State ---
        if (error) {
            return [
                <TableRow key="error">
                    <TableCell colSpan={numberOfColumns}>
                        <Alert variant="destructive" className="my-4">
                            <AlertCircle className="h-4 w-4" />
                            <AlertTitle>Erro ao Carregar Histórico</AlertTitle>
                            <AlertDescription>
                                Não foi possível buscar o histórico de importações. Tente novamente mais tarde.
                                {error.message && <p className="text-xs mt-1">Detalhe: {error.message}</p>}
                            </AlertDescription>
                        </Alert>
                    </TableCell>
                </TableRow>
            ];
        }

        // --- Empty State ---
        if (!data || data.items.length === 0) {
            return [
                <TableRow key="empty">
                    <TableCell colSpan={numberOfColumns} className="text-center text-muted-foreground py-8">
                        Nenhum histórico de importação encontrado.
                    </TableCell>
                </TableRow>
            ];
        }

        // --- Data Loaded State ---
        return data.items.flatMap((job: ImportJobListItem) => {
            const isExpanded = !!expandedRows[job.id];
            const isTerminal = job.status === 'COMPLETE' || job.status === 'FAILED';

            const mainRow = (
                <TableRow key={`main-${job.id}`} className={cn(isExpanded && "border-b-0")}>
                    {/* Expansion Trigger Cell */}
                    <TableCell className="w-[50px] px-2 align-middle">
                        {isTerminal ? (
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => toggleRowExpansion(job.id)}
                                aria-expanded={isExpanded}
                                aria-controls={`details-${job.id}`}
                                title={isExpanded ? "Ocultar Detalhes" : "Mostrar Detalhes"}
                            >
                                {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                                <span className="sr-only">
                                    {isExpanded ? "Ocultar Detalhes" : "Mostrar Detalhes"}
                                </span>
                            </Button>
                        ) : (
                            <div className="flex justify-center items-center h-8 w-8">
                                <Info className="h-4 w-4 text-muted-foreground" />
                            </div>
                        )}
                    </TableCell>

                    {/* Data Cells */}
                    <TableCell className="font-mono text-xs align-middle">
                        {job.id.substring(0, 8)}...
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate align-middle" title={job.original_filename ?? undefined}>
                        {job.original_filename || 'N/A'}
                    </TableCell>
                    <TableCell className="align-middle">
                        <Badge variant={getStatusVariant(job.status)}>{job.status || 'UNKNOWN'}</Badge>
                    </TableCell>
                    <TableCell className="align-middle">{formatDate(job.created_at)}</TableCell>
                    <TableCell className="align-middle">{formatDate(job.finished_at)}</TableCell>
                </TableRow>
            );

            const detailRow = isExpanded && isTerminal ? (
                <TableRow
                    key={`detail-${job.id}`}
                    id={`details-${job.id}`}
                    className="bg-muted/30 hover:bg-muted/40"
                >
                    <TableCell colSpan={numberOfColumns} className="p-0">
                        <JobStatusDetails jobId={job.id} fetchFn={authenticatedFetch} />
                    </TableCell>
                </TableRow>
            ) : null;

            return detailRow ? [mainRow, detailRow] : [mainRow];
        });
    };

    // Calculate pagination details
    const totalPages = data?.total_pages ?? 0;
    const totalItems = data?.total_items ?? 0;
    const startItem = totalItems > 0 ? (currentPage - 1) * ITEMS_PER_PAGE + 1 : 0;
    const endItem = data ? Math.min(startItem + ITEMS_PER_PAGE - 1, totalItems) : 0;

    return (
        <div>
            {/* Add overflow-hidden to ensure rounded corners clip correctly */}
            <div className="border rounded-md overflow-hidden">
                <Table>
                    <TableCaption className="mt-4 mb-2 px-4">
                        {totalItems > 0
                            ? `Mostrando ${startItem}-${endItem} de ${totalItems} importações.`
                            : ''}
                    </TableCaption>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[50px] px-2">
                                <span className="sr-only">Expandir</span>
                            </TableHead>
                            <TableHead className="w-[120px]">Job ID</TableHead>
                            <TableHead>Arquivo</TableHead>
                            <TableHead className="w-[100px]">Status</TableHead>
                            <TableHead className="w-[160px]">Iniciado em</TableHead>
                            <TableHead className="w-[160px]">Finalizado em</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {renderTableContent()}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
                <div className="flex items-center justify-end space-x-2 pt-4">
                    <span className="text-sm text-muted-foreground">
                        Página {currentPage} de {totalPages}
                    </span>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handlePreviousPage}
                        disabled={currentPage === 1 || isLoading}
                    >
                        <ChevronLeft className="h-4 w-4 mr-1" />
                        Anterior
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleNextPage}
                        disabled={currentPage === totalPages || isLoading}
                    >
                        Próxima
                        <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                </div>
            )}
        </div>
    );
};

export default ContactImportJobsTable;
