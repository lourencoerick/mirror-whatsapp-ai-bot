// src/components/chat/ConversationChatView.tsx

import React, { useCallback, useEffect, useRef, useState } from "react";
// Removed useParams, useSearchParams can stay if highlight is needed, or passed as prop
import { useSearchParams } from "next/navigation";
// Removed Link and ArrowLeft as navigation is handled by parent page
import {
  ChatBubble,
  ChatBubbleAvatar,
  ChatBubbleMessage,
} from "@/components/ui/chat/chat-bubble"; // Adjust path if needed
import { ChatInputBox } from "@/components/ui/chat/chat-input-box"; // Adjust path if needed
import { ChatMessage } from "@/components/ui/chat/chat-message"; // Adjust path if needed
import { ChatMessageList } from "@/components/ui/chat/chat-message-list"; // Adjust path if needed
import { ChatWebSocketBridge } from "@/components/ui/chat/chat-websocket-bridge"; // Adjust path if needed
import { useMessages } from "@/hooks/use-messages"; // Adjust path if needed
import { useSendMessage } from "@/hooks/use-send-message"; // Adjust path if needed
// Removed useLayoutContext
import { Button } from "@/components/ui/button"; // Adjust path if needed
import ConversationNotFound from "@/components/ui/conversation/conversation-notfound"; // Adjust path if needed
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"; // Adjust path if needed
import { Skeleton } from "@/components/ui/skeleton"; // Adjust path if needed
import api from "@/lib/api"; // Adjust path if needed
import { Conversation, ConversationStatusEnum } from "@/types/conversation"; // Adjust path if needed
import { Message } from "@/types/message"; // Adjust path if needed
import { Archive, MoreVertical, Play, Unlock } from "lucide-react"; // Removed ArrowLeft
import { toast } from "sonner";

interface ConversationChatViewProps {
  /** The unique identifier for the conversation to display. */
  conversationId: string;
  /** Optional: ID of a message to highlight initially. */
  highlightMessageId?: string | null;
  userDirection?: "in" | "out"; // <-- PROP ADICIONADA AQUI
}

/**
 * Component responsible for rendering the chat interface for a specific conversation.
 * Handles message fetching, display, sending, WebSocket updates, and status changes.
 * @param {ConversationChatViewProps} props - Component props.
 */
export function ConversationChatView({
  conversationId,
  highlightMessageId,
  userDirection = "out", // <-- PROP RECEBIDA E COM VALOR PADRÃO
}: ConversationChatViewProps) {
  // --- Hooks and State ---
  const searchParams = useSearchParams(); // Keep if highlight is still needed from URL
  // Use prop highlightMessageId if provided, otherwise fallback to URL searchParam
  const highlightId = highlightMessageId ?? searchParams.get("highlight");
  // Removed setPageTitle related state/hooks
  const messagesRef = useRef<HTMLDivElement>(null);

  const [input, setInput] = useState("");
  const [isAutoScrolling, setIsAutoScrolling] = useState(false); // Keep for scroll logic
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [conversationDetails, setConversationDetails] =
    useState<Conversation | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(true);
  const [fetchDetailsError, setFetchDetailsError] = useState<string | null>(
    null
  );

  // Use the conversationId prop in hooks
  const {
    messages,
    setMessages,
    loadingInitial,
    loadingOlder,
    loadingNewer,
    error: messagesError,
    hasMoreOlder,
    hasMoreNewer,
    loadOlderMessages,
    loadNewerMessages,
  } = useMessages(conversationId, highlightId); // Use prop

  const { sendMessage, sending, error: sendError } = useSendMessage();

  // Removed useEffect for setPageTitle

  // Fetch conversation details - uses conversationId prop
  const fetchConversationData = useCallback(async () => {
    if (!conversationId) return; // Check prop
    console.log(`Fetching details for conversation: ${conversationId}`); // Use prop
    setLoadingDetails(true);
    setFetchDetailsError(null);
    try {
      // Use prop in API call
      const response = await api.get<Conversation>(
        `/api/v1/conversations/${conversationId}`
      );
      setConversationDetails(response.data);
    } catch (err) {
      console.error("Error fetching conversation details:", err);
      setFetchDetailsError("Falha ao carregar detalhes da conversa.");
    } finally {
      setLoadingDetails(false);
    }
  }, [conversationId]); // Depend on prop

  useEffect(() => {
    fetchConversationData();
  }, [fetchConversationData]);

  // Update conversation status - uses conversationId prop
  const handleUpdateStatus = useCallback(
    async (newStatus: ConversationStatusEnum) => {
      if (!conversationId) return; // Check prop
      setIsUpdatingStatus(true);
      const previousDetails = conversationDetails;
      // Optimistic update
      setConversationDetails((prev) =>
        prev ? { ...prev, status: newStatus } : null
      );
      try {
        // Use prop in API call
        await api.put(`/api/v1/conversations/${conversationId}/status`, {
          status: newStatus,
        });
        toast.success(`Conversa marcada como ${newStatus.toLowerCase()}!`);
      } catch (err) {
        console.error("Failed to update conversation status:", err);
        toast.error("Falha ao atualizar status da conversa.");
        setConversationDetails(previousDetails); // Revert on error
      } finally {
        setIsUpdatingStatus(false);
      }
    },
    [conversationId, conversationDetails]
  ); // Depend on prop

  // Send message - uses conversationId prop
  const submitMessage = useCallback(async () => {
    if (!input.trim() || !conversationId) return; // Check prop
    try {
      await sendMessage(input.trim(), conversationId, userDirection); // <-- AJUSTE AQUI
      setInput("");
    } catch (err: unknown) {
      console.error("Error sending message:", err);
      // Error is handled by useSendMessage hook and displayed below input box
    }
    // Removed submitMessage from dependency array as it's defined in scope
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, conversationId, sendMessage, userDirection]); // Depend on prop and sendMessage hook

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) =>
    setInput(e.target.value);

  const handleSend = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      await submitMessage();
    },
    [submitMessage]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitMessage();
    }
  };

  // --- Scroll Handlers (Unchanged) ---
  const scrollToBottom = useCallback(() => {
    // ... (implementation unchanged) ...
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, []);

  const handleScroll = useCallback(() => {
    // ... (implementation unchanged) ...
    const element = messagesRef.current;
    if (!element || loadingOlder || loadingNewer || isAutoScrolling) return;
    const tolerance = 50;
    if (element.scrollTop <= tolerance && hasMoreOlder) {
      console.log("Requesting older messages");
      loadOlderMessages();
    }
    if (
      element.scrollHeight - element.scrollTop - element.clientHeight <=
        tolerance &&
      hasMoreNewer
    ) {
      console.log("Requesting newer messages");
      loadNewerMessages();
    }
  }, [
    loadOlderMessages,
    loadNewerMessages,
    hasMoreOlder,
    hasMoreNewer,
    loadingOlder,
    loadingNewer,
    isAutoScrolling,
  ]);

  useEffect(() => {
    // ... (implementation unchanged) ...
    const element = messagesRef.current;
    if (!element) return;
    element.addEventListener("scroll", handleScroll);
    return () => element.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  useEffect(() => {
    // ... (implementation unchanged) ...
    if (!loadingOlder) {
      setTimeout(scrollToBottom, 100);
    }
  }, [messages, loadingOlder, scrollToBottom]);

  // --- Loading Indicators (Unchanged) ---
  const renderOlderMessagesLoadingIndicator = () => {
    // ... (implementation unchanged) ...
    if (loadingOlder) {
      return (
        <div className="text-center py-2">
          <ChatBubble variant="received">
            <ChatBubbleAvatar src="" fallback="⏳" />
            <ChatBubbleMessage isLoading />
          </ChatBubble>
        </div>
      );
    }
    return null;
  };

  const renderNewerMessagesLoadingIndicator = () => {
    // ... (implementation unchanged) ...
    if (loadingNewer) {
      return (
        <div className="text-center py-2">
          <ChatBubble variant="received">
            <ChatBubbleAvatar src="" fallback="⏳" />
            <ChatBubbleMessage isLoading />
          </ChatBubble>
        </div>
      );
    }
    return null;
  };

  // --- Rendering ---
  // Removed outer page layout/title logic

  // Error fetching initial details
  if (fetchDetailsError && !loadingDetails) {
    return (
      <div className="p-4 text-center text-red-500">{fetchDetailsError}</div>
    );
  }

  // Main chat view structure
  return (
    // Use flex-grow if this component is placed within a flex container by parent
    <div className="flex flex-col w-full h-full bg-white dark:bg-neutral-900">
      {/* Header Section (Conversation Details & Actions) */}
      <div className="w-full p-2 border-b flex justify-between items-center gap-2 sticky top-0 bg-background z-10">
        <span className="text-sm font-medium truncate">
          {loadingDetails ? (
            <Skeleton className="h-5 w-40" />
          ) : (
            // Display contact name/phone from fetched details
            `Conversa com ${
              conversationDetails?.contact?.name ||
              conversationDetails?.contact?.phone_number ||
              "Desconhecido"
            }`
          )}
        </span>
        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleUpdateStatus(ConversationStatusEnum.CLOSED)}
            disabled={
              isUpdatingStatus ||
              loadingDetails ||
              conversationDetails?.status === ConversationStatusEnum.CLOSED
            }
            aria-label="Fechar Conversa"
          >
            <Archive className="h-4 w-4 mr-1" />
            Fechar
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                disabled={isUpdatingStatus || loadingDetails}
                aria-label="Mais opções"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() =>
                  handleUpdateStatus(ConversationStatusEnum.PENDING)
                }
                disabled={
                  isUpdatingStatus ||
                  loadingDetails ||
                  conversationDetails?.status === ConversationStatusEnum.PENDING
                }
              >
                <Unlock className="mr-2 h-4 w-4" />
                <span>Reabrir (Pendente)</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() =>
                  handleUpdateStatus(ConversationStatusEnum.HUMAN_ACTIVE)
                } // Assuming HUMAN_ACTIVE exists
                disabled={
                  isUpdatingStatus ||
                  loadingDetails ||
                  conversationDetails?.status ===
                    ConversationStatusEnum.HUMAN_ACTIVE
                }
              >
                <Play className="mr-2 h-4 w-4" />
                <span>Marcar como Ativa</span>
              </DropdownMenuItem>
              {/* Add other actions if needed */}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Message List Area */}
      <div
        className="w-full flex-grow overflow-y-auto px-4 mb-4"
        ref={messagesRef}
      >
        {renderOlderMessagesLoadingIndicator()}
        {/* WebSocket Bridge - uses conversationId prop */}
        <ChatWebSocketBridge
          conversationId={conversationId} // Use prop
          onNewMessage={(message) => {
            setMessages((prev: Message[]) => {
              // Prevent duplicate messages from WS
              if (prev.some((m) => m.id === message.id)) return prev;
              return [...prev, message];
            });
          }}
        />
        <ChatMessageList>
          {/* Initial Loading Skeleton */}
          {loadingInitial && !messagesError && (
            <ChatBubble variant="received">
              <ChatBubbleAvatar src="" fallback="⏳" />
              <ChatBubbleMessage isLoading />
            </ChatBubble>
          )}
          {/* Message Loading Error */}
          {messagesError && !loadingInitial && <ConversationNotFound />}
          {/* Render Messages */}
          {!messagesError &&
            messages.map((message, index) => (
              <ChatMessage
                key={message.id || index} // Use index as fallback key
                direction={message.direction}
                content={message.content}
                userDirection={userDirection}
                // Pass other message props if needed (timestamp, avatar, etc.)
              />
            ))}
        </ChatMessageList>
        {renderNewerMessagesLoadingIndicator()}
      </div>

      {/* Input Box Area */}
      <div className="w-full px-4 pb-4 pt-4 bg-background border-t">
        {" "}
        {/* Added border-t */}
        <ChatInputBox
          value={input}
          onChange={handleInputChange}
          onSubmit={handleSend}
          onKeyDown={handleKeyDown}
          disabled={sending || !input.trim()} // Disable while sending or if input is empty
        />
        {/* Display sending error */}
        {sendError && (
          <p className="text-red-500 text-xs text-center mt-2">{sendError}</p>
        )}
      </div>
    </div>
  );
}

// Export the component
export default ConversationChatView; // Use default export or named export as preferred
