import React, { forwardRef } from 'react';
import { ChatBubble, ChatBubbleAvatar, ChatBubbleMessage } from "@/components/ui/chat/chat-bubble";

interface ChatMessageProps {
  content: string;
  direction: "in" | "out";
  loading?: boolean;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export const ChatMessage = forwardRef<HTMLDivElement, ChatMessageProps>(({ content, direction, loading = false }, ref) => {
  return (
    <ChatBubble variant={direction === "out" ? "sent" : "received"}>
      <ChatBubbleAvatar src="" fallback={direction === "out" ? "🤖" : "👤"} />
      <ChatBubbleMessage isLoading={loading}>{content}</ChatBubbleMessage>
    </ChatBubble>
  );
}
);

ChatMessage.displayName = "ChatMessage";
