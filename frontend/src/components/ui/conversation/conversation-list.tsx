'use client';

import React, { useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import ConversationItem from './conversation-item';
import { useInfiniteConversations } from '@/hooks/use-conversations';
import { Conversation } from '@/types/conversation';


const ConversationsList: React.FC = () => {
  // Retrieve route parameters using Next.js useParams hook
  const params = useParams();
  // Assume the route provides conversationId
  const conversationId = params?.conversationId as string | undefined;


  // Use the custom infinite conversations hook
  const { conversations, loading, error, hasMore, loadMore } = useInfiniteConversations("11111111-1111-1111-1111-111111111111");

  // Create a ref for the element that triggers loading more conversations when visible
  const loaderRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Create an Intersection Observer to detect when the loader element enters the viewport
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          loadMore();
        }
      },
      { threshold: 1.0 }
    );

    if (loaderRef.current) {
      observer.observe(loaderRef.current);
    }

    // Cleanup observer on unmount or when dependencies change
    return () => {
      if (loaderRef.current) {
        observer.unobserve(loaderRef.current);
      }
    };
  }, [hasMore, loadMore, loading]);

  return (
    <div className="">
      {conversations.map((conversation: Conversation) => (
        <ConversationItem
          key={conversation.id}
          // Map API fields to the expected props of ConversationItem.
          id={conversation.id}
          phoneNumber={conversation.phone_number}
          contactName={conversation.contact_name}
          lastMessage={conversation.last_message?.content ?? ''}
          lastMessageTime={conversation.last_message_at}
          imageUrl={conversation.profile_picture_url}
          isSelected={conversation.id === conversationId}
        />
      ))}
      {error && <div className="p-4 text-red-500">Error loading conversations</div>}
      {loading && <div className="p-4">Loading...</div>}
      {/* This element is used by Intersection Observer to trigger loading more */}
      <div ref={loaderRef} />
    </div>
  );
};

export default ConversationsList;
