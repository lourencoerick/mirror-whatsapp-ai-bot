// components/JobStatusDetails.tsx
'use client';

import React from 'react';
import useSWR from 'swr';
import { AlertCircle } from 'lucide-react';

import { FetchFunction } from '@/hooks/use-authenticated-fetch'; 
import { getContactImportJobStatus } from '@/lib/api-client';
import { ContactImportJobStatusResponse } from '@/types/contact-import';


import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface JobStatusDetailsProps {
    jobId: string;
    fetchFn: FetchFunction;
}

/**
 * Fetches and displays the detailed status and result summary for a specific import job.
 * Intended to be used within a collapsible section of a table row.
 * @param {JobStatusDetailsProps} props - Component props.
 * @returns {React.ReactElement} The rendered component.
 */
const JobStatusDetails: React.FC<JobStatusDetailsProps> = ({ jobId, fetchFn }) => {

    const swrKey = jobId ? [`/api/v1/contacts/batch/import/status/${jobId}/details`, jobId] : null; // Unique key for details

    // Fetcher function specific to this component
    const fetcher = (
        [_url, currentJobId]: [string, string]
      ): Promise<ContactImportJobStatusResponse> => {
        // Use the fetchFn passed as a prop
        return getContactImportJobStatus(currentJobId, fetchFn);
      };

    const { data, error, isLoading } = useSWR<ContactImportJobStatusResponse>(
        swrKey,
        (key) => fetcher(key as [string, string]),
        {
            // Optional: configure revalidation behavior if needed
            revalidateOnFocus: false,
            dedupingInterval: 50000,
        }
    );

    // --- Loading State ---
    if (isLoading) {
        return (
            <div className="p-4 space-y-3">
                <Skeleton className="h-5 w-1/4" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-4 w-1/4" />
            </div>
        );
    }

    // --- Error State ---
    if (error) {
        return (
            <Alert variant="destructive" className="m-4">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Erro ao Carregar Detalhes</AlertTitle>
                <AlertDescription>
                    Não foi possível buscar os detalhes para o Job ID {jobId.substring(0, 8)}...
                    {error.message && <span className="block text-xs mt-1">Detalhe: {error.message}</span>}
                </AlertDescription>
            </Alert>
        );
    }

    // --- No Data State (Should ideally not happen if isLoading/error are handled) ---
     if (!data) {
        return <div className="p-4 text-muted-foreground">Nenhum detalhe disponível.</div>;
    }

    // --- Success State ---
    const { result_summary, status } = data;

    // Check if the job is in a state where a summary is expected
    const isTerminal = status === 'COMPLETE' || status === 'FAILED';

    if (!isTerminal) {
         return <div className="p-4 text-muted-foreground">O job ainda está em processamento ({status}). Detalhes estarão disponíveis após a finalização.</div>;
    }

    if (!result_summary) {
        return <div className="p-4 text-muted-foreground">Resumo da importação não disponível para este job ({status}).</div>;
    }

    // Render the summary details
    return (
        <Card className="m-2 shadow-inner bg-muted/50">
            <CardHeader className="pb-2 pt-4">
                <CardTitle className="text-base font-semibold">Resumo Detalhado da Importação</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm pb-4">
                <p>Linhas processadas: <span className="font-medium">{result_summary.total_rows_processed}</span></p>
                <p className="text-green-700 dark:text-green-500">
                    Importações com sucesso: <span className="font-medium">{result_summary.successful_imports}</span>
                </p>
                <p className="text-red-700 dark:text-red-500">
                    Falhas na importação: <span className="font-medium">{result_summary.failed_imports}</span>
                </p>
                {/* Error Details List */}
                {result_summary.failed_imports > 0 && result_summary.errors?.length > 0 && (
                    <div className="pt-3">
                        <h4 className="font-medium mb-1 text-xs text-muted-foreground uppercase tracking-wider">
                            Detalhes dos Erros ({result_summary.errors.length}):
                        </h4>
                        <div className="border rounded-md max-h-60 overflow-y-auto bg-background p-1">
                            <ul className="text-xs space-y-1 p-2">
                                {result_summary.errors.map((err, index) => (
                                    <li key={index} className="border-b border-dashed last:border-b-0 py-1">
                                        <span className="font-semibold">Linha {err.row_number}:</span> {err.reason}{" "}
                                        <pre className="text-muted-foreground/80 text-[10px] bg-muted p-1 rounded mt-0.5 overflow-x-auto">
                                            {JSON.stringify(err.data)}
                                        </pre>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                )}
                 {result_summary.failed_imports > 0 && !result_summary.errors?.length && (
                     <p className="text-xs text-muted-foreground pt-2">Nenhum detalhe específico de erro foi registrado.</p>
                 )}
            </CardContent>
        </Card>
    );
};

export default JobStatusDetails;