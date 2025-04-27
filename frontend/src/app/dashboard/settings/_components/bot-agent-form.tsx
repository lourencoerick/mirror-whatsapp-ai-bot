/* eslint-disable @typescript-eslint/no-explicit-any */
// app/dashboard/settings/_components/BotAgentForm.tsx
"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner"; // For user notifications
import * as z from "zod"; // Zod for schema validation

import { FetchFunction } from "@/hooks/use-authenticated-fetch";
import {
  getAgentInboxes,
  setAgentInboxes,
  updateMyBotAgent,
} from "@/lib/api/bot-agent"; // API calls for agent management
import { fetchInboxes } from "@/lib/api/inbox"; // API call for fetching inboxes
import { components } from "@/types/api"; // API type definitions

// UI Components
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { JSX } from "react/jsx-runtime";

// Type definitions from the generated API specification
type BotAgentRead = components["schemas"]["BotAgentRead"];
type BotAgentUpdate = components["schemas"]["BotAgentUpdate"];
type InboxRead = components["schemas"]["InboxRead"];

// Zod schema for form validation (pt-BR error messages)
const botAgentFormSchema = z.object({
  name: z
    .string()
    .min(1, "O nome do agente é obrigatório.")
    .max(255, "O nome do agente não pode exceder 255 caracteres."),
  first_message: z
    .string()
    .max(1000, "A mensagem inicial não pode exceder 1000 caracteres.")
    .nullable()
    .optional(), // Allow empty/null value
  use_rag: z.boolean().default(false),
  // inbox_ids are handled separately via state, not directly in this schema
});

// Type derived from the Zod schema
type BotAgentFormData = z.infer<typeof botAgentFormSchema>;

/**
 * Props for the BotAgentForm component.
 */
interface BotAgentFormProps {
  /** Initial data for the bot agent being edited, or null if creating. */
  initialAgentData: BotAgentRead | null;
  /** Authenticated fetch function for making API calls. */
  fetcher: FetchFunction;
  /** Callback function triggered when the agent is successfully updated. */
  onAgentUpdate: (updatedAgent: BotAgentRead) => void;
}

/**
 * Renders a form to configure Bot Agent settings, including name,
 * first message, RAG usage, and associated inboxes.
 * Handles fetching available inboxes, managing selections,
 * and submitting updates to the backend.
 * @param {BotAgentFormProps} props - The component props.
 * @returns {JSX.Element} The rendered form component.
 */
export function BotAgentForm({
  initialAgentData,
  fetcher,
  onAgentUpdate,
}: BotAgentFormProps): JSX.Element {
  const [availableInboxes, setAvailableInboxes] = useState<InboxRead[]>([]);
  const [selectedInboxIds, setSelectedInboxIds] = useState<Set<string>>(
    new Set()
  );
  const [isLoadingInboxes, setIsLoadingInboxes] = useState<boolean>(true);
  const [inboxError, setInboxError] = useState<string | null>(null);
  const agentId = initialAgentData?.id;

  const form = useForm<BotAgentFormData>({
    resolver: zodResolver(botAgentFormSchema),
    defaultValues: {
      name: initialAgentData?.name || "Assistente Principal", // Default name in pt-BR
      first_message: initialAgentData?.first_message || "",
      use_rag: initialAgentData?.use_rag || false,
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    control, // Needed for controlled components like Switch
  } = form;

  // Effect to load available inboxes and the agent's current associations
  useEffect(() => {
    /** Fetches all inboxes and the inboxes currently associated with this agent. */
    const loadInboxData = async () => {
      // Guard clause: Do nothing if fetcher or agent ID is missing
      if (!fetcher || !agentId) {
        setIsLoadingInboxes(false);
        return;
      }

      setIsLoadingInboxes(true);
      setInboxError(null);
      try {
        // Fetch all available inboxes and the agent's associated inboxes in parallel
        const [allInboxesResult, associatedInboxesResult] = await Promise.all([
          fetchInboxes(fetcher),
          getAgentInboxes(fetcher, agentId),
        ]);

        setAvailableInboxes(allInboxesResult || []);
        setSelectedInboxIds(
          new Set((associatedInboxesResult || []).map((inbox) => inbox.id))
        );
      } catch (error: any) {
        console.error("Falha ao carregar dados das caixas de entrada:", error);
        setInboxError(
          error.message || "Falha ao carregar as caixas de entrada."
        );
      } finally {
        setIsLoadingInboxes(false);
      }
    };

    loadInboxData();
  }, [fetcher, agentId]); // Re-run effect if fetcher or agentId changes

  // Effect to reset form values if the initial agent data changes
  useEffect(() => {
    if (initialAgentData) {
      reset({
        name: initialAgentData.name || "Assistente Principal",
        first_message: initialAgentData.first_message || "",
        use_rag: initialAgentData.use_rag || false,
      });
      // Also reset selected inboxes based on the new initial data (handled by the other effect)
    }
  }, [initialAgentData, reset]);

  /**
   * Handles changes to the inbox selection checkboxes.
   * @param {string} inboxId - The ID of the inbox being toggled.
   * @param {boolean | 'indeterminate'} checked - The new checked state.
   */
  const handleInboxChange = (
    inboxId: string,
    checked: boolean | "indeterminate"
  ) => {
    // We only care about boolean checked states (not indeterminate)
    if (typeof checked === "boolean") {
      setSelectedInboxIds((prev) => {
        const newSet = new Set(prev);
        if (checked) {
          newSet.add(inboxId);
        } else {
          newSet.delete(inboxId);
        }
        return newSet;
      });
    }
  };

  /**
   * Handles the form submission process.
   * Updates the agent's basic settings and associated inboxes via API calls.
   * Shows success or error notifications to the user.
   * @param {BotAgentFormData} formData - The validated form data.
   */
  const onSubmit = async (formData: BotAgentFormData) => {
    if (!agentId) {
      toast.error("Não foi possível salvar as configurações do agente", {
        description: "ID do agente ausente.",
      });
      return;
    }

    const inboxIdsToSave = Array.from(selectedInboxIds); // Convert Set to Array for API

    try {
      // Prepare the payload for updating agent settings
      const agentPayload: BotAgentUpdate = { ...formData };

      // Perform API calls in parallel: update agent details and set associated inboxes
      const [updatedAgent] = await Promise.all([
        updateMyBotAgent(fetcher, agentId, agentPayload),
        setAgentInboxes(fetcher, agentId, inboxIdsToSave),
      ]);

      toast.success("Sucesso!", {
        description: "Configurações do Vendedor IA atualizadas com sucesso.",
      });

      // If the agent update was successful, notify the parent component
      if (updatedAgent) {
        onAgentUpdate(updatedAgent);
      }
    } catch (error: any) {
      console.error("Falha ao atualizar configurações do agente:", error);
      toast.error("Erro ao atualizar configurações", {
        description: error.message || "Ocorreu um erro inesperado.",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configurações do Vendedor IA</CardTitle>
        <CardDescription>
          Configure o comportamento e as conexões para o seu Vendedor IA.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="space-y-6">
          {/* Agent Basic Settings Section */}
          <div>
            <Label className="mb-1.5 block" htmlFor="agent-name">
              Nome do Agente
            </Label>
            <Input
              id="agent-name"
              {...register("name")}
              disabled={isSubmitting}
            />
            {errors.name && (
              <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>
            )}
          </div>

          <div>
            <Label className="mb-1.5 block" htmlFor="first-message">
              Mensagem Inicial
            </Label>
            <Textarea
              id="first-message"
              rows={3}
              placeholder="Opcional: Deixe em branco para aguardar a mensagem do usuário..."
              {...register("first_message")}
              disabled={isSubmitting}
            />
            {errors.first_message && (
              <p className="text-xs text-red-600 mt-1">
                {errors.first_message.message}
              </p>
            )}
          </div>

          <div className="flex items-center space-x-2 pt-2">
            {/* Controller is required for integrating react-hook-form with custom/UI library components like Switch */}
            <Controller
              name="use_rag"
              control={control}
              render={({ field }) => (
                <Switch
                  id="use_rag"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  aria-readonly={isSubmitting}
                  disabled={isSubmitting} // Consider disabling if RAG feature is not fully implemented or available
                />
              )}
            />
            <Label className="cursor-pointer" htmlFor="use_rag">
              Usar Base de Conhecimento (RAG)
            </Label>
            {errors.use_rag && (
              <p className="text-xs text-red-600 mt-1">
                {errors.use_rag.message}
              </p>
            )}
          </div>

          {/* Inbox Association Section */}
          <div className="pt-2">
            <Label className="mb-1.5 block">Caixas de Entrada Associadas</Label>
            <p className="text-sm text-muted-foreground mb-3">
              Selecione as caixas de entrada que este agente deve gerenciar.
            </p>
            {isLoadingInboxes ? (
              // Show skeletons while loading inboxes
              <div className="space-y-2">
                <Skeleton className="h-6 w-1/2" />
                <Skeleton className="h-6 w-2/3" />
                <Skeleton className="h-6 w-1/3" />
              </div>
            ) : inboxError ? (
              // Show error message if loading failed
              <p className="text-sm text-red-600">{inboxError}</p>
            ) : availableInboxes.length === 0 ? (
              // Show message if no inboxes are available
              <p className="text-sm text-muted-foreground italic">
                Nenhuma caixa de entrada encontrada para esta conta.{" "}
                <Link href="/dashboard/inboxes/new" className="underline">
                  Criar uma?
                </Link>
              </p>
            ) : (
              // Display the list of available inboxes
              <div className="space-y-3 rounded-md border p-4 max-h-60 overflow-y-auto">
                {availableInboxes.map((inbox) => {
                  // Determine if the checkbox should be disabled
                  const isAssociatedWithOtherAgent =
                    inbox.associated_bot_agent_id != null &&
                    inbox.associated_bot_agent_id !== agentId;
                  const isDisabled = isSubmitting || isAssociatedWithOtherAgent;
                  const initialStatus =
                    inbox.initial_conversation_status || "Padrão"; // Use 'Padrão' if null
                  const isSelected = selectedInboxIds.has(inbox.id);
                  // Determine if a warning is needed (selected but status is not BOT)
                  const needsWarning = isSelected && initialStatus !== "BOT";

                  return (
                    <div key={inbox.id} className="space-y-1.5">
                      {/* Container for Checkbox and Label */}
                      <div
                        className="flex items-center space-x-2"
                        title={
                          isAssociatedWithOtherAgent
                            ? "Esta caixa de entrada já está atribuída a outro agente."
                            : ""
                        }
                      >
                        <Checkbox
                          id={`inbox-${inbox.id}`}
                          checked={isSelected}
                          onCheckedChange={(checked) =>
                            handleInboxChange(inbox.id, checked)
                          }
                          disabled={isDisabled}
                          aria-describedby={
                            isAssociatedWithOtherAgent
                              ? `inbox-disabled-desc-${inbox.id}`
                              : needsWarning
                              ? `inbox-warning-desc-${inbox.id}`
                              : undefined
                          }
                        />
                        <Label
                          htmlFor={`inbox-${inbox.id}`}
                          className={`font-normal cursor-pointer ${
                            // Apply styles for disabled states
                            isDisabled && !isSelected
                              ? "text-muted-foreground line-through cursor-not-allowed"
                              : ""
                          } ${
                            isDisabled && isSelected
                              ? "text-muted-foreground cursor-not-allowed"
                              : ""
                          }`}
                        >
                          {inbox.name}{" "}
                          <span className="text-xs text-muted-foreground">
                            ({inbox.channel_type})
                          </span>
                          {/* Screen reader text for disabled state */}
                          {isAssociatedWithOtherAgent && (
                            <span
                              id={`inbox-disabled-desc-${inbox.id}`}
                              className="sr-only"
                            >
                              (Atribuído a outro agente)
                            </span>
                          )}
                        </Label>
                      </div>

                      {/* Warning Alert: Displayed below if the inbox is selected but not set to 'BOT' status */}
                      {needsWarning && (
                        <Alert
                          variant="default"
                          // Indent the alert slightly
                          className="ml-6 max-w-fit border-yellow-400 bg-yellow-50 text-yellow-800"
                        >
                          <AlertCircle className="h-4 w-4 !text-yellow-600" />
                          <AlertDescription
                            id={`inbox-warning-desc-${inbox.id}`}
                            className="flex flex-col sm:flex-row text-xs"
                          >
                            <span>
                              Novas conversas iniciam como &apos;{initialStatus}
                              &apos;. Altere nas configurações da caixa de
                              entrada para &apos;BOT&apos; para resposta
                              imediata da IA.
                            </span>
                            {/* Optional: Link to directly edit the inbox settings */}
                            <Link
                              href={`/dashboard/inboxes/${inbox.id}/settings`}
                              className="underline ml-0 mt-1 sm:ml-1 sm:mt-0 font-medium whitespace-nowrap"
                              target="_blank" // Open in new tab for convenience
                              rel="noopener noreferrer"
                            >
                              Editar Caixa de Entrada
                            </Link>
                          </AlertDescription>
                        </Alert>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </CardContent>
        <CardFooter className="mt-4 flex justify-end border-t pt-6">
          <Button
            type="submit"
            disabled={isSubmitting || isLoadingInboxes} // Disable button during submission or initial loading
          >
            {(isSubmitting || isLoadingInboxes) && (
              // Show loading spinner when busy
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Salvar Configurações do Vendedor IA
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
