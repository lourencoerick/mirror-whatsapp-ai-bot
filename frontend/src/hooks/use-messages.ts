import { useState, useEffect } from 'react';
import { AxiosResponse } from 'axios';
import api from '@/lib/api';
import { Message } from "@/types/message"

/**
 * Custom React hook to fetch messages for a given conversation ID.
 *
 * This hook calls the backend API endpoint `/conversations/:id/messages`
 * and returns the message list along with loading and error state.
 *
 * @param conversationId - The ID of the conversation to fetch messages for.

 * @returns An object containing:
 *  - `messages`: List of messages sorted by date.
 *  - `setMessages`: setMessage action ot update messages
 *  - `loading`: Boolean indicating whether data is being fetched.
 *  - `error`: Boolean indicating if an error occurred during fetch.
 */
export function useMessages(conversationId: string): {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  loading: boolean;
  error: boolean;
} {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<boolean>(false);

  useEffect(() => {
    async function fetchMessages(): Promise<void> {
      try {
        setLoading(true);
        const res: AxiosResponse<Message[]> = await api.get(
          `/conversations/${conversationId}/messages`
        );
        setMessages(res.data.reverse());
      } catch (err: unknown) {
        console.error('Error fetching messages', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    }

    if (conversationId) {
      fetchMessages();
    }
  }, [conversationId]);

  return { messages, setMessages, loading, error };
}
