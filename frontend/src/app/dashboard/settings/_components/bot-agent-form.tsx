// app/dashboard/settings/_components/BotAgentForm.tsx
"use client";

import { FetchFunction } from "@/hooks/use-authenticated-fetch";
import {
  getAgentInboxes,
  setAgentInboxes,
  updateMyBotAgent,
} from "@/lib/api/bot-agent"; // API calls for agent
import { fetchInboxes } from "@/lib/api/inbox"; // API call for inboxes
import { components } from "@/types/api";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import * as z from "zod"; // Import zod

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox"; // Import Checkbox
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch"; // Import Switch
import { Textarea } from "@/components/ui/textarea";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

// Types from generated API spec
type BotAgentRead = components["schemas"]["BotAgentRead"];
type BotAgentUpdate = components["schemas"]["BotAgentUpdate"];
type InboxRead = components["schemas"]["InboxRead"];

// Zod schema for BotAgent form validation
const botAgentFormSchema = z.object({
  name: z.string().min(1, "Agent name is required").max(255),
  first_message: z.string().max(1000).nullable().optional(), // Allow empty/null
  is_active: z.boolean().default(false),
  use_rag: z.boolean().default(false),
  // We'll handle inbox_ids separately, not directly in this schema
});

type BotAgentFormData = z.infer<typeof botAgentFormSchema>;

interface BotAgentFormProps {
  initialAgentData: BotAgentRead | null;
  fetcher: FetchFunction;
  onAgentUpdate: (updatedAgent: BotAgentRead) => void;
}

export function BotAgentForm({
  initialAgentData,
  fetcher,
  onAgentUpdate,
}: BotAgentFormProps) {
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
      name: initialAgentData?.name || "Primary Assistant",
      first_message: initialAgentData?.first_message || "",
      is_active: initialAgentData?.is_active || false,
      use_rag: initialAgentData?.use_rag || false,
    },
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
    control,
  } = form;

  // Fetch available inboxes and currently associated inboxes on mount/agent change
  useEffect(() => {
    const loadInboxData = async () => {
      if (!fetcher || !initialAgentData?.id) {
        setIsLoadingInboxes(false); // Stop loading if no agent ID or fetcher
        return;
      }

      setIsLoadingInboxes(true);
      setInboxError(null);
      try {
        const [InboxRead, associatedInboxesResult] = await Promise.all([
          fetchInboxes(fetcher),
          getAgentInboxes(fetcher, initialAgentData.id),
        ]);

        setAvailableInboxes(InboxRead || []);
        setSelectedInboxIds(
          new Set((associatedInboxesResult || []).map((inbox) => inbox.id))
        );
      } catch (error: any) {
        console.error("Failed to load inbox data:", error);
        setInboxError(error.message || "Failed to load inboxes.");
      } finally {
        setIsLoadingInboxes(false);
      }
    };

    loadInboxData();
  }, [fetcher, initialAgentData?.id]); // Re-run if fetcher or agent ID changes

  // Reset form if initial agent data changes
  useEffect(() => {
    if (initialAgentData) {
      reset({
        name: initialAgentData.name || "Primary Assistant",
        first_message: initialAgentData.first_message || "",
        is_active: initialAgentData.is_active || false,
        use_rag: initialAgentData.use_rag || false,
      });
    }
  }, [initialAgentData, reset]);

  const handleInboxChange = (
    inboxId: string,
    checked: boolean | "indeterminate"
  ) => {
    if (typeof checked === "boolean") {
      setSelectedInboxIds((prev) => {
        const newSet = new Set(prev);
        if (checked) {
          newSet.add(inboxId);
        } else {
          newSet.delete(inboxId);
        }
        console.log("Selected Inbox IDs:", Array.from(newSet)); // Log para debug
        return newSet;
      });
    }
  };

  const onSubmit = async (formData: BotAgentFormData) => {
    if (!initialAgentData?.id) {
      toast.error("Cannot save agent settings", {
        description: "Agent ID is missing.",
      });
      return;
    }
    console.log("Agent form data submitted:", formData);
    const inboxIdsToSave = Array.from(selectedInboxIds); // Converter Set para Array
    console.log("Selected Inbox IDs:", Array.from(selectedInboxIds));

    try {
      // 1. Update Agent Settings
      const agentPayload: BotAgentUpdate = { ...formData };
      const [updatedAgent] = await Promise.all([
        // Executa em paralelo
        updateMyBotAgent(fetcher, initialAgentData.id, agentPayload),
        setAgentInboxes(fetcher, initialAgentData.id, inboxIdsToSave),
      ]);

      toast.success("Success!", {
        description: "AI Seller settings updated successfully.",
      });
      if (updatedAgent) {
        onAgentUpdate(updatedAgent); // Notify parent page
      }
    } catch (error: any) {
      console.error("Failed to update agent settings:", error);
      toast.error("Error updating settings", {
        description: error.message || "An unexpected error occurred.",
      });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI Seller Settings</CardTitle>
        <CardDescription>
          Configure the behavior and connections for your AI Seller.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(onSubmit)}>
        <CardContent className="space-y-6">
          {/* --- Basic Settings --- */}
          <div>
            <Label className="mb-1.5 block" htmlFor="agent-name">
              Agent Name
            </Label>
            <Input id="agent-name" {...register("name")} />
            {errors.name && (
              <p className="text-xs text-red-600 mt-1">{errors.name.message}</p>
            )}
          </div>

          <div>
            <Label className="mb-1.5 block" htmlFor="first-message">
              First Message
            </Label>
            <Textarea
              id="first-message"
              rows={3}
              placeholder="Optional: Leave empty to wait for user..."
              {...register("first_message")}
            />
            {errors.first_message && (
              <p className="text-xs text-red-600 mt-1">
                {errors.first_message.message}
              </p>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {/* Need Controller for Switch */}
            <Controller
              name="is_active"
              control={control}
              render={({ field }) => (
                <Switch
                  id="is_active"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  aria-readonly={isSubmitting}
                  disabled={isSubmitting}
                />
              )}
            />
            <Label className="mb-1.5 block" htmlFor="is_active">
              Agent Active
            </Label>
            {errors.is_active && (
              <p className="text-xs text-red-600 mt-1">
                {errors.is_active.message}
              </p>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {/* Need Controller for Switch */}
            <Controller
              name="use_rag"
              control={control}
              render={({ field }) => (
                <Switch
                  id="use_rag"
                  checked={field.value}
                  onCheckedChange={field.onChange}
                  aria-readonly={isSubmitting}
                  disabled={isSubmitting} // TODO: Disable if RAG feature not ready
                />
              )}
            />
            <Label className="mb-1.5 block" htmlFor="use_rag">
              Use Knowledge Base (RAG)
            </Label>
            {errors.use_rag && (
              <p className="text-xs text-red-600 mt-1">
                {errors.use_rag.message}
              </p>
            )}
          </div>

          {/* --- Inbox Association --- */}
          <div>
            <Label className="mb-1.5 block">Associated Inboxes</Label>
            <p className="text-sm text-muted-foreground mb-2">
              Select the inboxes this agent should handle.
            </p>
            {isLoadingInboxes ? (
              <div className="space-y-2">
                <Skeleton className="h-6 w-1/2" />
                <Skeleton className="h-6 w-2/3" />
              </div>
            ) : inboxError ? (
              <p className="text-sm text-red-600">{inboxError}</p>
            ) : availableInboxes.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">
                No inboxes found for this account.
              </p>
            ) : (
              <div className="space-y-2 rounded-md border p-4 max-h-60 overflow-y-auto">
                {availableInboxes.map((inbox) => {
                  // --- Lógica para desabilitar ---
                  const isAssociatedWithOtherAgent =
                    inbox.associated_agent_id != null &&
                    inbox.associated_agent_id !== agentId;
                  const isDisabled = isSubmitting || isAssociatedWithOtherAgent;
                  // --- Fim da Lógica ---
                  return (
                    <div
                      key={inbox.id}
                      className="flex items-center space-x-2"
                      title={
                        isAssociatedWithOtherAgent
                          ? "This inbox is already assigned to another agent."
                          : ""
                      }
                    >
                      <Checkbox
                        id={`inbox-${inbox.id}`}
                        checked={selectedInboxIds.has(inbox.id)}
                        onCheckedChange={(checked) =>
                          handleInboxChange(inbox.id, checked)
                        }
                        disabled={isDisabled} // Usar a variável isDisabled
                        aria-describedby={
                          isAssociatedWithOtherAgent
                            ? `inbox-disabled-desc-${inbox.id}`
                            : undefined
                        }
                      />
                      <Label
                        htmlFor={`inbox-${inbox.id}`}
                        className={`font-normal cursor-pointer ${
                          isDisabled && !selectedInboxIds.has(inbox.id)
                            ? "text-muted-foreground line-through"
                            : ""
                        } ${
                          isDisabled && selectedInboxIds.has(inbox.id)
                            ? "text-muted-foreground"
                            : ""
                        }`}
                      >
                        {inbox.name}{" "}
                        <span className="text-xs">({inbox.channel_type})</span>
                        {isAssociatedWithOtherAgent && (
                          <span
                            id={`inbox-disabled-desc-${inbox.id}`}
                            className="sr-only"
                          >
                            (Assigned to another agent)
                          </span>
                        )}
                      </Label>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </CardContent>
        <CardFooter className="flex justify-end">
          <Button
            className="mt-4 ml-auto"
            type="submit"
            disabled={isSubmitting || isLoadingInboxes}
          >
            {(isSubmitting || isLoadingInboxes) && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Save AI Seller Settings
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
