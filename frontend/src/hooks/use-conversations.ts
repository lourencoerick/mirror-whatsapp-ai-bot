import { useState, useEffect, useCallback } from 'react';
import { AxiosResponse } from 'axios';
import api from '../lib/api';
import { useConversationSocket } from '@/hooks/use-conversation-socket';
import { Conversation, UseInfiniteConversationsResult } from '@/types/conversation';

const CONVERSATIONS_LIMIT: number = 10;

/**
 * Custom hook to fetch conversations with infinite scrolling and real-time updates via WebSocket.
 *
 * Uses limit and offset for pagination and also integrates WebSocket events to:
 * - Add a new conversation if it does not exist
 * - Update an existing conversation
 *
 * @param accountId - The current authenticated account ID.
 *
 * @returns An object containing the conversation list, loading state, error state,
 * a flag indicating if more conversations exist, and a function to load more.
 */
export function useInfiniteConversations(accountId: string): UseInfiniteConversationsResult {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [offset, setOffset] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<boolean>(false);
  const [hasMore, setHasMore] = useState<boolean>(true);

  // Function to load more conversations via API
  const loadMore = useCallback((): void => {
    if (loading || !hasMore) return;

    setLoading(true);
    api
      .get<Conversation[]>(`/conversations`, {
        params: { limit: CONVERSATIONS_LIMIT, offset: offset },
      })
      .then((response: AxiosResponse<Conversation[]>) => {
        const newConversations = response.data;
        setConversations((prevConversations) => {
          console.log('Previous conversations before API load:', prevConversations);
          const updatedConversations = [...prevConversations, ...newConversations];
          console.log('Updated conversations after API load:', updatedConversations);
          return updatedConversations;
        });
        setOffset((prevOffset) => prevOffset + newConversations.length);
        if (newConversations.length < CONVERSATIONS_LIMIT) {
          setHasMore(false);
        }
      })
      .catch((err: unknown) => {
        console.error('Error fetching conversations:', err);
        setError(true);
      })
      .finally(() => setLoading(false));
  }, [loading, hasMore, offset]);

  // Initial load
  useEffect(() => {
    setConversations([]);
    setOffset(0);
    setHasMore(true);
    loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Integration with WebSocket for real-time updates
  useConversationSocket(accountId, {
    onNewConversation: (newConv) => {
      console.log('Socket event: new conversation received', newConv);
      setConversations((prev) => {
        console.log('Previous conversations before adding new conversation:', prev);
        const exists = prev.some((c) => c.id === newConv.id);
        if (exists) {
          console.log('Conversation already exists:', newConv.id);
          return prev;
        }
        const updatedConversations = [newConv, ...prev];
        console.log('Updated conversations after adding new conversation:', updatedConversations);
        return updatedConversations;
      });
    },
