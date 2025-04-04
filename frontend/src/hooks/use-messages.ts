import { useState, useEffect, useCallback, useRef } from 'react';
import { AxiosResponse } from 'axios';
import api from '@/lib/api';
import { Message } from "@/types/message";

const MESSAGES_PER_PAGE = 10;

function sortAndDeduplicateMessages(messages: Message[]): Message[] {
  const seenIds = new Set<string>();
  const uniqueMessages: Message[] = [];
  for (const message of messages) {
    if (!seenIds.has(message.id)) {
      seenIds.add(message.id);
      uniqueMessages.push(message);
    }
  }
  uniqueMessages.sort((a, b) => {
    const timeA = new Date(a.sent_at || 0).getTime();
    const timeB = new Date(b.sent_at || 0).getTime();
    if (timeA !== timeB) return timeA - timeB;
    return a.id.localeCompare(b.id);
  });
  return uniqueMessages;
}

export function useMessages(
  conversationId: string | null,
  highlightMessageId: string | null
): {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  loadingInitial: boolean;
  loadingOlder: boolean;
  loadingNewer: boolean;
  error: string | null;
  hasMoreOlder: boolean;
  hasMoreNewer: boolean;
  loadOlderMessages: () => void;
  loadNewerMessages: () => void;
} {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingInitial, setLoadingInitial] = useState<boolean>(false);
  const [loadingOlder, setLoadingOlder] = useState<boolean>(false);
  const [loadingNewer, setLoadingNewer] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMoreOlder, setHasMoreOlder] = useState<boolean>(true);
  const [hasMoreNewer, setHasMoreNewer] = useState<boolean>(false);

  const oldestMessageCursorRef = useRef<string | null>(null);
  const newestMessageCursorRef = useRef<string | null>(null);
  const isLoading = useRef<boolean>(false);
  const initialLoadWasContext = useRef<boolean>(false);

  // --- Reset State Effect ---
  useEffect(() => {
    // This effect runs when conversationId changes
    resetState();
  }, [conversationId]);

  const resetState = useCallback(() => {
    console.log("Resetting state due to conversationId change.");
    setMessages([]);
    setError(null);
    setHasMoreOlder(true);
    setHasMoreNewer(false);
    oldestMessageCursorRef.current = null;
    newestMessageCursorRef.current = null;
    initialLoadWasContext.current = false;
    isLoading.current = false;
    setLoadingInitial(false);
  }, []);


  // --- Initial Data Load Effect ---
  useEffect(() => {
    if (!conversationId) return; // Do nothing if no conversationId

    const performInitialLoad = async () => {
      if (isLoading.current) return;

      console.log(`Initial load effect running: convId=${conversationId}, highlightId=${highlightMessageId}`);
      initialLoadWasContext.current = !!highlightMessageId;
      isLoading.current = true;
      setLoadingInitial(true);
      setError(null);

      try {
        let initialMessages: Message[] = [];
        let fetchedHasMoreOlder = true;
        let fetchedHasMoreNewer = false;

        if (highlightMessageId) {
          // --- Carga Inicial de Contexto ---
          const contextUrl = `/api/v1/conversations/${conversationId}/messages/context/${highlightMessageId}`;
          const contextParams = { limit_before: MESSAGES_PER_PAGE / 2, limit_after: MESSAGES_PER_PAGE / 2 };
          console.log("Fetching initial context...", contextParams);
          const response: AxiosResponse<Message[]> = await api.get(contextUrl, { params: contextParams });
          initialMessages = response.data;
          console.log(`Context fetched: ${initialMessages.length} messages.`);

          if (initialMessages.length > 0) {
            const highlightIndex = initialMessages.findIndex(m => m.id === highlightMessageId);
            fetchedHasMoreOlder = highlightIndex > 0 && highlightIndex >= (contextParams.limit_before || 1);
            fetchedHasMoreNewer = (initialMessages.length - 1 - highlightIndex) >= (contextParams.limit_after || 1);

             if(highlightIndex === 0) fetchedHasMoreOlder = false;
             if(highlightIndex === initialMessages.length - 1) fetchedHasMoreNewer = false;

          } else {
            fetchedHasMoreOlder = false;
            fetchedHasMoreNewer = false;
          }

        } else {
          // --- Carga Inicial Normal (Mais Recentes) ---
          const latestParams = { limit: MESSAGES_PER_PAGE };
          const url = `/api/v1/conversations/${conversationId}/messages`;
          console.log("Fetching initial latest messages...", latestParams);
          const response: AxiosResponse<Message[]> = await api.get(url, { params: latestParams });
          initialMessages = response.data;
          console.log(`Latest messages fetched: ${initialMessages.length} messages.`);
          fetchedHasMoreNewer = false;
          fetchedHasMoreOlder = initialMessages.length === MESSAGES_PER_PAGE;
        }

        const processedMessages = sortAndDeduplicateMessages(initialMessages);
        setMessages(processedMessages);
        setHasMoreOlder(fetchedHasMoreOlder);
        setHasMoreNewer(fetchedHasMoreNewer);

        if (processedMessages.length > 0) {
          oldestMessageCursorRef.current = processedMessages[0].id;
          newestMessageCursorRef.current = processedMessages[processedMessages.length - 1].id;
          console.log("Initial cursors set:", oldestMessageCursorRef.current, newestMessageCursorRef.current);
          console.log("Initial hasMore:", fetchedHasMoreOlder, fetchedHasMoreNewer);
        } else {
          oldestMessageCursorRef.current = null;
          newestMessageCursorRef.current = null;
           console.log("No initial messages, cursors cleared.");
        }

      } catch (err: unknown) {
        console.error("Error during initial load:", err);
        setError(err instanceof Error ? err.message : "Failed initial load");
        setHasMoreOlder(false);
        setHasMoreNewer(false);
      } finally {
        isLoading.current = false;
        setLoadingInitial(false);
      }
    };

    performInitialLoad();

  }, [conversationId, highlightMessageId, resetState]); // Depend on resetState to avoid stale state

  // --- Função Genérica para Buscar Mensagens Paginadas (Older/Newer) ---
  const fetchPaginatedMessages = useCallback(async (direction: 'older' | 'newer') => {
      if (isLoading.current) return;
      if (direction === 'older' && !hasMoreOlder) return;
      if (direction === 'newer' && !hasMoreNewer) return;

      const cursor = direction === 'older' ? oldestMessageCursorRef.current : newestMessageCursorRef.current;
      if (!cursor) {
          console.warn(`Cannot load ${direction} messages without a cursor.`);
          return;
      }

      isLoading.current = true;
      if (direction === 'older') setLoadingOlder(true);
      else setLoadingNewer(true);
      setError(null);

      const params: { limit: number; before_cursor?: string; after_cursor?: string } = {
          limit: MESSAGES_PER_PAGE,
      };
      if (direction === 'older') {
          params.before_cursor = cursor;
      } else {
          params.after_cursor = cursor;
      }

      const url = `/api/v1/conversations/${conversationId}/messages`;
      console.log(`Fetching ${direction} messages with params:`, params);

      try {
          const response: AxiosResponse<Message[]> = await api.get(url, { params });
          const fetchedMessages = response.data;
          console.log(`Fetched ${fetchedMessages.length} ${direction} messages.`);

          if (fetchedMessages.length > 0) {
              setMessages(prevMessages => {
                  const combined = direction === 'older'
                      ? [...fetchedMessages, ...prevMessages]
                      : [...prevMessages, ...fetchedMessages];
                  return sortAndDeduplicateMessages(combined);
              });

              if (direction === 'older') {
                  oldestMessageCursorRef.current = fetchedMessages[0].id;
              } else {
                  newestMessageCursorRef.current = fetchedMessages[fetchedMessages.length - 1].id;
              }
          }

          if (direction === 'older') {
              setHasMoreOlder(fetchedMessages.length === MESSAGES_PER_PAGE);
          } else {
              setHasMoreNewer(fetchedMessages.length === MESSAGES_PER_PAGE);
          }

      } catch (err: unknown) {
          console.error(`Error fetching ${direction} messages:`, err);
          setError(err instanceof Error ? err.message : `Failed to fetch ${direction} messages`);
          if (direction === 'older') setHasMoreOlder(false);
          else setHasMoreNewer(false);
      } finally {
          isLoading.current = false;
          setLoadingOlder(false);
          setLoadingNewer(false);
      }
  }, [conversationId, hasMoreOlder, hasMoreNewer]);

  const loadOlderMessages = useCallback(() => {
    fetchPaginatedMessages('older');
  }, [fetchPaginatedMessages]);

  const loadNewerMessages = useCallback(() => {
    fetchPaginatedMessages('newer');
  }, [fetchPaginatedMessages]);

  return {
    messages,
    setMessages,
    loadingInitial,
    loadingOlder,
    loadingNewer,
    error,
    hasMoreOlder,
    hasMoreNewer,
    loadOlderMessages,
    loadNewerMessages,
  };
}