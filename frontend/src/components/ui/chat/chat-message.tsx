import {
  ChatBubble,
  ChatBubbleAvatar,
  ChatBubbleMessage,
} from "@/components/ui/chat/chat-bubble";
import { forwardRef } from "react";

interface ChatMessageProps {
  content: string;
  direction: "in" | "out";
  loading?: boolean;
  userDirection?: "in" | "out";
}

export const ChatMessage = forwardRef<HTMLDivElement, ChatMessageProps>(
  ({ content, direction, loading = false, userDirection = "out" }, ref) => {
    const isUserMsg = direction === userDirection;

    const variant = isUserMsg ? "sent" : "received";
    const avatarFallback = isUserMsg ? "👤" : "🤖";

    return (
      <ChatBubble variant={variant} ref={ref}>
        <ChatBubbleAvatar src="" fallback={avatarFallback} />
        <ChatBubbleMessage isLoading={loading}>{content}</ChatBubbleMessage>
      </ChatBubble>
    );
  }
);

ChatMessage.displayName = "ChatMessage";
