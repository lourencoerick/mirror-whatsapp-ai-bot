
'use client';

import React, { useState, ChangeEvent, FormEvent, useRef } from 'react';

import { useSWRConfig } from 'swr';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
    DialogClose,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

import { FileUp, AlertCircle, CheckCircle2, Loader2, UploadCloud } from 'lucide-react';

import { useAuthenticatedFetch } from '@/hooks/use-authenticated-fetch'; // Adjust path

interface ImportJobStartResponse {
    id: string;
    status: string;
}

// Define the type for the message state
type MessageStateType = {
    text: string;
    type: 'info' | 'success' | 'error';
};

/**
 * A simplified dialog component solely for uploading a CSV file to initiate
 * a contact import job. Closes automatically on successful initiation.
 * @component
 */
const ContactImportDialog: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
    const [message, setMessage] = useState<MessageStateType | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const authenticatedFetch = useAuthenticatedFetch();
    // Keep mutate to refresh the jobs list table
    const { mutate } = useSWRConfig();

    // --- Event Handlers ---

    /** Resets the component state to initial values. */
    const resetState = () => {
        console.log("Resetting dialog state..."); // Debug log
        // Removed jobId reset
        setMessage(null);
        setSelectedFile(null);
        setIsSubmitting(false);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    /**
     * Handles changes to the file input element.
     * Updates the selected file state after validation.
     * @param {ChangeEvent<HTMLInputElement>} event - The input change event.
     */
    const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
        console.log("File input changed:", event.target.files);
        setMessage(null);
        if (event.target.files && event.target.files.length > 0) {
            const file = event.target.files[0];
            console.log("File selected:", file.name, file.type);
            if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
                setSelectedFile(file);
                console.log("Selected file state set:", file.name);
            } else {
                setMessage({ text: 'Por favor, selecione um arquivo .csv válido.', type: 'error' });
                setSelectedFile(null);
                if (fileInputRef.current) fileInputRef.current.value = '';
                console.log("Invalid file type, selection cleared.");
            }
        } else {
            setSelectedFile(null);
            console.log("No file selected or dialog cancelled.");
        }
    };

    /** Programmatically clicks the hidden file input element. */
    const handleSelectFileClick = () => {
        console.log("Select file button clicked.");
        if (message?.type === 'error') setMessage(null);
        fileInputRef.current?.click();
    };

    /**
     * Handles the form submission to upload the selected file.
     * On success (202), triggers a refresh of the job list and closes the dialog.
     * @param {FormEvent<HTMLFormElement>} event - The form submission event.
     */
    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!selectedFile || isSubmitting) return;

        setIsSubmitting(true);
        setMessage({ text: `Enviando ${selectedFile.name}...`, type: 'info' });

        const formData = new FormData();
        formData.append('file', selectedFile, selectedFile.name);
        const endpoint = '/api/v1/contacts/batch/import';

        try {
            const response = await authenticatedFetch(endpoint, {
                method: 'POST',
                body: formData,
                headers: { 'Accept': 'application/json', 'Content-Type': '' }
            });

            if (response.status === 202) {
                const data: ImportJobStartResponse = await response.json();
                if (!data.id) {

                    throw new Error('Resposta da API inválida: ID do job não encontrado.');
                }
                console.log("Job initiated successfully:", data.id);



                const listKey = [`/api/v1/contacts/batch/import/jobs`, 1, 10];
                console.log("Mutating job list table SWR key:", listKey);
                mutate(listKey);




                setMessage(null);
                setIsOpen(false);
                resetState();

            } else {

                let errorText = `Falha no envio: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    errorText = errorData.detail || errorText;
                } catch { /* Ignore */ }
                throw new Error(errorText);
            }
        } catch (error: any) {
            console.error("Error submitting file:", error);
            setMessage({ text: `Erro ao enviar arquivo: ${error.message || 'Tente novamente.'}`, type: 'error' });
        } finally {
            setIsSubmitting(false);
        }
    };

    /**
     * Handles the dialog open/close state changes.
     * Resets the component state when the dialog is closed.
     * @param {boolean} open - The new open state of the dialog.
     */
    const handleOpenChange = (open: boolean) => {
        setIsOpen(open);
        if (!open) {
            resetState();
        }
    };

    // --- Rendering Logic ---

    /** Renders the current alert message based on component state (simplified). */
    const renderAlert = () => {
        if (!message) return null;


        let variant: "default" | "destructive" = "default";
        let Icon = CheckCircle2;

        if (message.type === 'error') {
            variant = "destructive";
            Icon = AlertCircle;
        } else if (message.type === 'info' && isSubmitting) {

            Icon = Loader2;
        }
        return (
            <Alert variant={variant} className="mt-4">
                <Icon className={`h-4 w-4 ${Icon === Loader2 ? 'animate-spin' : ''}`} />
                <AlertTitle>
                    {message.type === 'error' ? 'Erro' : 'Informação'}
                </AlertTitle>
                <AlertDescription>{message.text}</AlertDescription>
            </Alert>
        );
    };


    // --- Component Return ---
    return (
        <Dialog open={isOpen} onOpenChange={handleOpenChange}>
            {/* Button that triggers the dialog */}
            <DialogTrigger asChild>
                <Button variant="outline">
                    <UploadCloud className="mr-2 h-4 w-4" />
                    Importar Contatos
                </Button>
            </DialogTrigger>

            {/* Content of the Dialog - Simplified */}
            <DialogContent className="sm:max-w-[525px]">
                <DialogHeader>
                    <DialogTitle>Importar Contatos via CSV</DialogTitle>
                    <DialogDescription>
                        Selecione um arquivo .csv com as colunas: `name`, `phone_number`. Coluna `email` é opcional.
                    </DialogDescription>
                </DialogHeader>

                {/* Form is always visible now */}
                <form onSubmit={handleSubmit}>
                    <div className="grid gap-4 py-4">
                        <div className="grid w-full items-center gap-1.5">
                            {/* Hidden file input */}
                            <Input
                                ref={fileInputRef}
                                id="csvFile"
                                type="file"
                                accept=".csv, text/csv"
                                onChange={handleFileChange}
                                className="hidden"
                                disabled={isSubmitting}
                            />
                            {/* Button to trigger file input */}
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleSelectFileClick}
                                disabled={isSubmitting}
                            >
                                <FileUp className="mr-2 h-4 w-4" />
                                {selectedFile
                                    ? `Trocar: ${selectedFile.name.substring(0, 20)}${selectedFile.name.length > 20 ? '...' : ''}`
                                    : "Escolher Arquivo CSV"}
                            </Button>
                            {/* Display selected file name */}
                            {selectedFile && (
                                <p className="text-sm text-muted-foreground mt-1">
                                    Arquivo pronto para envio: {selectedFile.name}
                                </p>
                            )}
                        </div>
                        {/* Display alerts related to file selection or submission */}
                        {renderAlert()}
                    </div>
                    <DialogFooter>
                        {/* Cancel button closes the dialog via DialogClose */}
                        <DialogClose asChild>
                            <Button type="button" variant="ghost" disabled={isSubmitting}>
                                Cancelar
                            </Button>
                        </DialogClose>
                        {/* Submit button */}
                        <Button type="submit" disabled={!selectedFile || isSubmitting}>
                            {isSubmitting ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Enviando...
                                </>
                            ) : (
                                "Enviar e Iniciar Importação"
                            )}
                        </Button>
                    </DialogFooter>
                </form>
                {/* Removed the conditional rendering part for status details */}
            </DialogContent>
        </Dialog>
    );
};

export default ContactImportDialog;