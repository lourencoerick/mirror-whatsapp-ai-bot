import { useState, useEffect, useCallback } from 'react';
import { AxiosResponse } from 'axios';
import api from '../lib/api';

export interface Conversation {
  id: number;
  profile_picture_url: string;
  phone_number: string;
  contact_name: string;
  last_message_at: string;
  last_message: {
    content: string;
    created_at: string;
  } | null;
}

interface UseInfiniteConversationsResult {
  conversations: Conversation[];
  loading: boolean;
  error: boolean;
  hasMore: boolean;
  loadMore: () => void;
}

const CONVERSATIONS_LIMIT: number = 10;

/**
 * Custom hook to fetch conversations with infinite scrolling.
 * Uses limit and offset for pagination.
 *
 * @param inboxId - The ID of the inbox to fetch conversations for.
 * @returns An object containing the conversations list, loading state, error state,
 * a flag indicating if more conversations exist, and a function to load more.
 */
export function useInfiniteConversations(inboxId: string): UseInfiniteConversationsResult {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [offset, setOffset] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<boolean>(false);
  const [hasMore, setHasMore] = useState<boolean>(true);

  // loadMore now only depends on inboxId
  const loadMore = useCallback((): void => {
    // If already loading or no more items, do nothing
    if (loading || !hasMore) return;

    setLoading(true);
    api
      .get<Conversation[]>(`/inboxes/${inboxId}/conversations`, {
        params: { limit: CONVERSATIONS_LIMIT, offset: offset },
      })
      .then((response: AxiosResponse<Conversation[]>) => {
        const newConversations = response.data;
        setConversations((prevConversations) => [
          ...prevConversations,
          ...newConversations,
        ]);
        // Update offset using functional update to avoid adding offset to dependencies
        setOffset((prevOffset) => prevOffset + newConversations.length);
        // If fewer items than limit were returned, there are no more items to load
        if (newConversations.length < CONVERSATIONS_LIMIT) {
          setHasMore(false);
        }
      })
      .catch((err: unknown) => {
        console.error('Error fetching conversations:', err);
        setError(true);
      })
      .finally(() => setLoading(false));
    // Notice: we are not including offset, loading or hasMore in the dependencies.
  }, [inboxId, loading, hasMore, offset]);

  // Initial load only when inboxId changes. We remove loadMore from dependencies to avoid loop.
  useEffect(() => {
    setConversations([]);
    setOffset(0);
    setHasMore(true);
    loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inboxId]);

  return { conversations, loading, error, hasMore, loadMore };
}
