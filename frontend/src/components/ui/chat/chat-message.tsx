import { ChatBubble, ChatBubbleAvatar, ChatBubbleMessage } from "@/components/ui/chat/chat-bubble";

interface ChatMessageProps {
  content: string;
  direction: "in" | "out";
  loading?: boolean;
}

export function ChatMessage({ content, direction, loading = false }: ChatMessageProps) {
  return (
    <ChatBubble variant={direction === "out" ? "sent" : "received"}>
      <ChatBubbleAvatar src="" fallback={direction === "out" ? "🤖" : "👤"} />
      <ChatBubbleMessage isLoading={loading}>{content}</ChatBubbleMessage>
    </ChatBubble>
  );
}
