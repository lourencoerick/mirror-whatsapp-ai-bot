import { useState } from "react";
import { sendMessage } from "@/lib/actions/send-message";

/**
 * Hook to send a message and manage loading/error state.
 */
export function useSendMessage() {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSend(content: string, conversationId: string) {
    setSending(true);
    setError(null);

    try {
      await sendMessage({ content, conversationId });
    } catch (err) {
      console.error("[useSendMessage]", err);
      setError("Erro ao enviar mensagem");
    } finally {
      setSending(false);
    }
  }

  return { sendMessage: handleSend, sending, error };
}
