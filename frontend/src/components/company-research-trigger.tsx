// components/CompanyResearchTrigger.tsx
"use client";

import { Loader2, Wand2 } from "lucide-react"; // Icons
import React, { useState } from "react";
import { toast } from "sonner"; // For user feedback notifications

import { FetchFunction } from "@/hooks/use-authenticated-fetch"; // Type for authenticated fetch function
import { startResearch } from "@/lib/api/research"; // API function to start research (adjust path if needed)
import { components } from "@/types/api"; // Generated API types

// UI Components
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
} from "@/components/ui/alert-dialog"; // Confirmation dialog
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { JSX } from "react/jsx-runtime";

// Type definition for the expected API response
type ResearchResponse = components["schemas"]["ResearchResponse"];

/**
 * Props for the CompanyResearchTrigger component.
 */
interface CompanyResearchTriggerProps {
  /** Authenticated fetch function for making API calls. */
  fetcher: FetchFunction;
  /** Indicates whether a company profile already exists for the account. */
  profileExists: boolean;
  /** Optional flag to disable the component, e.g., while another research job is active. */
  disabled?: boolean;
  /** Callback function triggered when research is successfully started, passing the job ID or null on failure. */
  onResearchStarted: (jobId: string | null) => void;
}

/**
 * Renders a card component allowing users to input a website URL
 * and trigger an AI-powered research process to generate or update
 * the company profile. Includes confirmation if overwriting an existing profile.
 * @param {CompanyResearchTriggerProps} props - The component props.
 * @returns {JSX.Element} The rendered research trigger component.
 */
export function CompanyResearchTrigger({
  fetcher,
  profileExists,
  disabled = false, // Default disabled state to false
  onResearchStarted,
}: CompanyResearchTriggerProps): JSX.Element {
  // State for the website URL input
  const [url, setUrl] = useState<string>("");
  // State to track loading status during API call
  const [isLoading, setIsLoading] = useState<boolean>(false);
  // State to store and display error messages
  const [error, setError] = useState<string | null>(null);

  /** Updates the URL state and clears any previous error when the input changes. */
  const handleUrlChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(event.target.value.trim()); // Trim whitespace from input
    setError(null); // Clear error on input change
  };

  /**
   * Initiates the company profile research process by calling the backend API.
   * Handles loading state, error reporting, and success notification.
   */
  const triggerResearch = async () => {
    // Basic validation before API call
    if (!url) {
      setError("Por favor, insira uma URL de website válida.");
      return; // Exit if URL is empty
    }
    if (!fetcher) {
      setError("Função de busca (fetcher) não disponível.");
      setIsLoading(false); // Should not happen, but good practice
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Call the actual API function to start the research job
      const result: ResearchResponse = await startResearch(fetcher, url);

      if (result && result.job_id) {
        toast.success("Pesquisa iniciada!", {
          description: `Tarefa ${result.job_id} enfileirada. O perfil será atualizado em breve.`,
        });
        setUrl(""); // Clear the input field on success
        onResearchStarted(result.job_id); // Notify parent component with the job ID
      } else {
        // The API function should ideally throw an error on failure,
        // but handle potential non-error responses without job_id as errors too.
        throw new Error(
          result?.message || "Falha ao iniciar a tarefa de pesquisa."
        );
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      const errorMessage = err.message || "Ocorreu um erro inesperado.";
      console.error("Erro ao iniciar pesquisa:", err);
      setError(errorMessage); // Display error message near the input
      toast.error("Falha ao iniciar pesquisa", { description: errorMessage });
      onResearchStarted(null); // Notify parent component that starting failed
    } finally {
      setIsLoading(false); // Ensure loading state is reset
    }
  };

  /**
   * Handles the click event for the main trigger button.
   * Performs basic URL validation before allowing the AlertDialog to open.
   * Note: The actual API call (`triggerResearch`) is invoked by the AlertDialog's Action button.
   */
  const handleButtonClick = () => {
    // Validate URL before allowing the dialog trigger to proceed
    if (!url) {
      setError("Por favor, insira uma URL primeiro.");
      // Prevent the dialog from opening by not doing anything further.
      // The button's disabled state should already handle this, but added as a safeguard.
      return;
    }
    // Clear any previous error when attempting to trigger
    setError(null);
    // The AlertDialogTrigger component handles opening the dialog.
    // No need to call triggerResearch() here directly.
  };

  // Determine button text based on whether a profile exists
  const buttonText = profileExists
    ? "Atualizar Perfil pelo Website"
    : "Gerar Perfil pelo Website";

  // Determine if the main trigger button should be disabled
  const isButtonDisabled = isLoading || disabled || !url;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <Wand2 className="mr-2 h-5 w-5 text-indigo-600" />
          Geração Automatizada de Perfil
        </CardTitle>
        <CardDescription>
          Insira a URL do website da empresa para gerar ou atualizar
          automaticamente o perfil da empresa usando IA.
          {profileExists && (
            <span className="font-medium text-orange-600">
              {" "}
              Isso sobrescreverá edições manuais.
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Label htmlFor="research-url" className="mb-1.5 block">
            URL do Website
          </Label>
          <Input
            type="url"
            id="research-url"
            value={url}
            onChange={handleUrlChange}
            placeholder="https://www.exemplo.com.br"
            required
            disabled={isLoading || disabled} // Disable input during loading or if externally disabled
            aria-invalid={!!error} // Indicate invalid state for accessibility
            aria-describedby={error ? "research-url-error" : undefined}
          />
        </div>
        {/* Display error message below the input */}
        {error && (
          <p
            id="research-url-error"
            className="text-sm text-red-600"
            role="alert"
          >
            {error}
          </p>
        )}
      </CardContent>
      <CardFooter className="flex justify-end">
        {/* Use AlertDialog to confirm overwrite if profile exists */}
        <AlertDialog>
          <AlertDialogTrigger asChild>
            {/* This button opens the confirmation dialog */}
            <Button
              onClick={handleButtonClick} // Performs basic validation before opening dialog
              disabled={isButtonDisabled}
            >
              {isLoading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Wand2 className="mr-2 h-4 w-4" />
              )}
              {isLoading ? "Iniciando..." : buttonText}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {profileExists
                  ? "Confirmar Sobrescrita do Perfil?"
                  : "Confirmar Geração de Perfil?"}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {profileExists
                  ? `Gerar um perfil a partir de "${url}" sobrescreverá quaisquer alterações manuais feitas no perfil atual da empresa. Tem certeza que deseja continuar?`
                  : `Iniciar a geração de um novo perfil com base no conteúdo de "${url}"?`}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setError(null)}>
                Cancelar
              </AlertDialogCancel>
              {/* This action button triggers the actual API call */}
              <AlertDialogAction onClick={triggerResearch}>
                {profileExists ? "Sobrescrever e Gerar" : "Gerar Perfil"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardFooter>
    </Card>
  );
}
