/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { useAuthenticatedFetch } from "@/hooks/use-authenticated-fetch";

// Import API functions
import { sendMessage as sendAgentMessage } from "@/lib/actions/send-message";
import { sendSimulationMessage } from "@/lib/api/simulation";

// Import Types
import { components } from "@/types/api";
type SimulationMessageEnqueueResponse =
  components["schemas"]["SimulationMessageEnqueueResponse"];
type MessageResponse = components["schemas"]["MessageResponse"];

// Helper to get the query key for messages list
const getMessagesQueryKey = (conversationId: string) => [
  "messages",
  conversationId,
];

/**
 * Hook to handle sending messages within a conversation (Simplified: No Optimistic Updates).
 * Calls the appropriate API endpoint based on user direction.
 * For agent messages ('out'), adds the response to the cache.
 * For simulation messages ('in'), relies on WebSocket to add the message later.
 */
export function useSendMessage() {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const fetcher = useAuthenticatedFetch();

  /**
   * Sends a message via the appropriate API endpoint.
   *
   * @param {string} content - The text content of the message.
   * @param {string} conversationId - The ID of the target conversation.
   * @param {'in' | 'out'} userDirection - The intended direction ('in' for simulation, 'out' for agent).
   */
  const sendMessage = useCallback(
    async (
      content: string,
      conversationId: string,
      userDirection: "in" | "out"
    ) => {
      if (!fetcher) {
        const authError = "Authentication context not available.";
        setError(authError);
        toast.error(authError);
        return;
      }
      if (!content || !conversationId) return;

      setSending(true);
      setError(null);
      const queryKey = getMessagesQueryKey(conversationId);

      try {
        // --- API Call (Conditional) ---
        if (userDirection === "in") {
          // Call the simulation endpoint - It only enqueues
          console.log(`Calling sendSimulationMessage (no optimistic update)`);
          const enqueueResponse: SimulationMessageEnqueueResponse =
            await sendSimulationMessage(fetcher, conversationId, content);
          console.log(
            `Simulation message enqueued successfully:`,
            enqueueResponse
          );
          toast.info("Mensagem simulada enviada para processamento.");
        } else {
          // userDirection === 'out'
          // Call the standard agent message endpoint
          console.log(`Calling sendAgentMessage (no optimistic update)`);
          const sentMessage: MessageResponse = await sendAgentMessage({
            content: content,
            conversationId: conversationId,
          });
          console.log(`Agent message sent successfully:`, sentMessage);
          queryClient.setQueryData<MessageResponse[]>(queryKey, (old = []) => {
            if (old.some((m) => m.id === sentMessage.id)) {
              return old;
            }
            return [...old, sentMessage];
          });
          // Opcional: Invalidar a query para garantir consistência, embora setQueryData geralmente baste.
          // queryClient.invalidateQueries({ queryKey });
        }
      } catch (err: any) {
        const errorMsg =
          err.message || `Falha ao enviar mensagem (${userDirection}).`;
        setError(errorMsg);
        toast.error(`Falha ao enviar mensagem: ${errorMsg}`);
        console.error(
          `Error sending message (direction: ${userDirection}):`,
          err
        );
      } finally {
        setSending(false);
      }
    },
    [queryClient, fetcher]
  );

  return { sendMessage, sending, error };
}
