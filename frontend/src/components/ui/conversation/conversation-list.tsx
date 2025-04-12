'use client';

import React, { useEffect, useRef } from 'react';
import { useParams } from 'next/navigation'; // For conversationId
import ConversationItem from './conversation-item';
import { useInfiniteConversations, ConversationFilters } from '@/hooks/use-conversations';
import { Conversation } from '@/types/conversation';

interface ConversationsListProps {
  socketIdentifier: string;
  filters: ConversationFilters;
}

const ConversationsList: React.FC<ConversationsListProps> = ({ socketIdentifier, filters }) => {
  // Get selected conversationId from route params
  const params = useParams();
  const conversationId = params?.conversationId as string | undefined;

  // Fetch conversations using the provided filters
  const { conversations, loading, error, hasMore, loadMore } = useInfiniteConversations(
    socketIdentifier,
    filters
  );

  // Ref for the infinite scroll trigger element
  const loaderRef = useRef<HTMLDivElement | null>(null);

  // Intersection Observer to trigger loadMore
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          console.log("Intersection observer triggered loadMore");
          loadMore();
        }
      },
      { threshold: 1.0 }
    );

    const currentLoader = loaderRef.current;
    if (currentLoader) {
      observer.observe(currentLoader);
    }

    return () => {
      if (currentLoader) {
        observer.unobserve(currentLoader);
      }
    };
  }, [hasMore, loadMore, loading]);

  return (
    <>
      {/* Render conversations list */}
      {!loading &&
        conversations.map((conversation: Conversation) => (
          <ConversationItem
            key={conversation.id}
            id={conversation.id}
            phoneNumber={conversation.contact?.phone_number ?? ''}
            contactName={conversation.contact?.name ?? ''}
            imageUrl={conversation.contact?.profile_picture_url ?? ''}
            lastMessageContent={conversation.last_message?.content ?? ''}
            lastMessageTime={conversation.updated_at}
            unreadCount={conversation.unread_agent_count}
            status={conversation.status}
            matchingMessageId={conversation.matching_message?.id ?? null}
            matchingMessageContent={conversation.matching_message?.content ?? null}
            isSelected={conversation.id === conversationId}
          />
        ))}

      {/* Loading indicator */}
      {loading && <div className="p-4 text-center text-gray-500 w-xs">Carregando...</div>}

      {/* Error message */}
      {error && <div className="p-4 text-center text-red-500 w-xs">Erro ao carregar conversas.</div>}

      {/* Empty state message */}
      {!loading && !error && conversations.length === 0 && (
        <div className="p-4 text-center text-gray-500 w-xs">
          {filters.query
            ? `Nenhuma conversa encontrada para "${filters.query}".`
            : 'Nenhuma conversa encontrada para este filtro.'}
        </div>
      )}

      {/* Infinite scroll trigger element */}
      {hasMore && <div ref={loaderRef} style={{ height: '1px' }} />}
    </>
  );
};

export default ConversationsList;
