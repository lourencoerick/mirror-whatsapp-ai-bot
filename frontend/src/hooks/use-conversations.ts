import { useState, useEffect, useCallback, useRef } from "react";
import { AxiosResponse } from "axios";
import api from "@/lib/api";
import { useConversationSocket } from "@/hooks/use-conversation-socket";
import {
  Conversation,
  ConversationStatusEnum,
  UseInfiniteConversationsResult,
} from "@/types/conversation";

const CONVERSATIONS_LIMIT: number = 15;

// Helper to remove duplicate conversations based on ID
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

export interface ConversationFilters {
  query?: string | null;
  status?: ConversationStatusEnum[] | null;
  has_unread?: boolean | null;
}

/**
 * Custom hook to fetch conversations with infinite scrolling,
 * filtering, and real-time updates.
 */
export function useInfiniteConversations(
  socketIdentifier: string,
  filters: ConversationFilters
): UseInfiniteConversationsResult {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadingInitial, setLoadingInitial] = useState<boolean>(false);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(true);

  // Refs to manage state without causing re-renders
  const currentOffset = useRef<number>(0);
  const isLoading = useRef<boolean>(false);
  const activeFilters = useRef<ConversationFilters>(filters);
  const hasMoreRef = useRef(hasMore);

  useEffect(() => {
    hasMoreRef.current = hasMore;
  }, [hasMore]);

  // Function to fetch conversations
  const fetchConversations = useCallback(async (isInitialLoad: boolean) => {
    if (isLoading.current || (!isInitialLoad && !hasMoreRef.current)) {
      console.log("Fetch skipped:", {
        isLoading: isLoading.current,
        isInitialLoad,
        currentHasMore: hasMoreRef.current,
      });
      return;
    }

    isLoading.current = true;
    const currentFilters = activeFilters.current;

    if (isInitialLoad) {
      setLoadingInitial(true);
      currentOffset.current = 0;
      setHasMore(true);
      setError(null);
    } else {
      setLoadingMore(true);
    }

    const params: {
      limit: number;
      offset: number;
      q?: string;
      status?: string[];
      has_unread?: string;
    } = {
      limit: CONVERSATIONS_LIMIT,
      offset: currentOffset.current,
    };

    const trimmedQuery = currentFilters.query?.trim();
    if (trimmedQuery) params.q = trimmedQuery;
    if (currentFilters.status && currentFilters.status.length > 0)
      params.status = currentFilters.status;
    if (currentFilters.has_unread !== null && currentFilters.has_unread !== undefined)
      params.has_unread = String(currentFilters.has_unread);

    console.log(`Fetching conversations: filters=${JSON.stringify(params)}`);

    try {
      const response: AxiosResponse<Conversation[]> = await api.get<Conversation[]>(
        `/api/v1/conversations`,
        { params }
      );
      const newConversations = response.data;

      setConversations((prevConversations) => {
        const combined = isInitialLoad
          ? newConversations
          : [...prevConversations, ...newConversations];
        return deduplicateConversations(combined);
      });

      currentOffset.current += newConversations.length;
      setHasMore(newConversations.length === CONVERSATIONS_LIMIT);
    } catch (err: unknown) {
      console.error("Error fetching conversations:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch conversations.");
      setHasMore(false);
    } finally {
      setLoadingInitial(false);
      setLoadingMore(false);
      isLoading.current = false;
    }
  }, []);

  // Trigger initial load or re-fetch when filters change
  useEffect(() => {
    console.log(`Filters changed: ${JSON.stringify(filters)}. Triggering fetch.`);
    activeFilters.current = filters;
    fetchConversations(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [socketIdentifier, JSON.stringify(filters), fetchConversations]);

  // Callback to load more data
  const loadMore = useCallback(() => {
    console.log("loadMore called...");
    fetchConversations(false);
  }, [fetchConversations]);

  // WebSocket integration for real-time updates
  useConversationSocket(socketIdentifier, {
    onNewConversation: (newConv) => {
      console.log("Socket event: new conversation received", newConv);
      setConversations((prev) => deduplicateConversations([newConv, ...prev]));
    },
    onConversationUpdate: (updatedConv) => {
      console.log("Socket event: conversation update received", updatedConv);
      setConversations((prev) => {
        const index = prev.findIndex((c) => c.id === updatedConv.id);
        let updatedList: Conversation[];
        if (index === -1) {
          console.warn(`Updated conversation ${updatedConv.id} not found in list, adding.`);
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
