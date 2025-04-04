import { useState, useEffect, useCallback, useRef } from "react";
import { AxiosResponse } from "axios";
import api from "../lib/api";
import { useConversationSocket } from "@/hooks/use-conversation-socket";
import {
  Conversation,
  UseInfiniteConversationsResult,
} from "@/types/conversation";

const CONVERSATIONS_LIMIT: number = 15;

/**
 * Deduplicates an array of conversations based on conversation id.
 * Keeps the first occurrence found.
 * @param conversations An array of Conversation objects.
 * @returns A new array with only unique conversations.
 */
function deduplicateConversations(
  conversations: Conversation[]
): Conversation[] {
  const seenIds = new Set<string>();
  const result: Conversation[] = [];
  for (const conversation of conversations) {
    if (!seenIds.has(conversation.id)) {
      seenIds.add(conversation.id);
      result.push(conversation);
    }
  }
  return result;
}

/**
 * Custom hook to fetch conversations with infinite scrolling and real-time updates via WebSocket.
 * Handles search queries and ensures state consistency during query changes.
 *
 * @param socketIdentifier - Identifier for WebSocket connection.
 * @param query - Optional search query string.
 *
 * @returns An object implementing UseInfiniteConversationsResult.
 */
export function useInfiniteConversations(
  socketIdentifier: string,
  query: string | null
): UseInfiniteConversationsResult {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadingInitial, setLoadingInitial] = useState<boolean>(false);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(true);

  const currentOffset = useRef<number>(0);
  const isLoading = useRef<boolean>(false);

  const activeQuery = useRef<string | null>(query);

  const fetchConversations = useCallback(async (isInitialLoad: boolean) => {
    if (isLoading.current) return;
    if (!isInitialLoad && !hasMore) return;

    isLoading.current = true;
    const currentQuery = activeQuery.current;

    if (isInitialLoad) {
      setLoadingInitial(true);
      currentOffset.current = 0;
      setHasMore(true);
      setError(null);
    } else {
      setLoadingMore(true);
    }

    const params: { limit: number; offset: number; q?: string } = {
      limit: CONVERSATIONS_LIMIT,
      offset: currentOffset.current,
    };

    const trimmedQuery = currentQuery?.trim();
    if (trimmedQuery) {
      params.q = trimmedQuery;
    }

    console.log(
      `Fetching conversations: query="${params.q ?? "(none)"}", offset=${
        params.offset
      }`
    );

    try {
      const response: AxiosResponse<Conversation[]> = await api.get<
        Conversation[]
      >(`/api/v1/conversations`, { params });
      const newConversations = response.data;

      setConversations((prevConversations) => {
        const combined =
          isInitialLoad || currentQuery !== activeQuery.current
            ? newConversations
            : [...prevConversations, ...newConversations];
        return deduplicateConversations(combined);
      });

      currentOffset.current += newConversations.length;

      setHasMore(newConversations.length === CONVERSATIONS_LIMIT);
    } catch (err: unknown) {
      console.error("Error fetching conversations:", err);
      setError(
        err instanceof Error ? err.message : "Falha ao buscar conversas."
      );
      setHasMore(false);
    } finally {
      setLoadingInitial(false);
      setLoadingMore(false);
      isLoading.current = false;
    }
  }, []);

  useEffect(() => {
    console.log(`Initial load effect triggered. Query changed to: "${query}"`);
    activeQuery.current = query;
    setConversations([]);
    fetchConversations(true);
  }, [socketIdentifier, query, fetchConversations]);

  const loadMore = useCallback(() => {
    console.log("loadMore called...");
    fetchConversations(false);
  }, [fetchConversations]);

  useConversationSocket(socketIdentifier, {
    onNewConversation: (newConv) => {
      console.log("Socket event: new conversation received", newConv);
      setConversations((prev) => {
        return deduplicateConversations([newConv, ...prev]);
      });
    },
    onConversationUpdate: (updatedConv) => {
      console.log("Socket event: conversation update received", updatedConv);
      setConversations((prev) => {
        const index = prev.findIndex((c) => c.id === updatedConv.id);
        let updatedList: Conversation[];
        if (index === -1) {
          updatedList = [updatedConv, ...prev];
        } else {
          updatedList = [...prev];
          updatedList[index] = updatedConv;
        }
        return deduplicateConversations(updatedList);
      });
    },
  });

  return {
    conversations,
    loading: loadingInitial || loadingMore,
    error: error ? true : false,
    hasMore,
    loadMore,
  };
}
