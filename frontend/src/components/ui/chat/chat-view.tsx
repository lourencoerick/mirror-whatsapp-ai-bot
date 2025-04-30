// src/components/chat/ConversationChatView.tsx

import { Button } from "@/components/ui/button";
import {
  ChatBubble,
  ChatBubbleAvatar,
  ChatBubbleMessage,
} from "@/components/ui/chat/chat-bubble";
import { ChatInputBox } from "@/components/ui/chat/chat-input-box";
import { ChatMessage } from "@/components/ui/chat/chat-message";
import { ChatMessageList } from "@/components/ui/chat/chat-message-list";
import { ChatWebSocketBridge } from "@/components/ui/chat/chat-websocket-bridge";
import ConversationNotFound from "@/components/ui/conversation/conversation-notfound";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useMessages } from "@/hooks/use-messages";
import { useSendMessage } from "@/hooks/use-send-message";
import api from "@/lib/api";
import { cn } from "@/lib/utils";
import { Conversation, ConversationStatusEnum } from "@/types/conversation";
import { Message } from "@/types/message";
import { Archive, ArrowDown, MoreVertical, Play, Unlock } from "lucide-react";
import { useSearchParams } from "next/navigation";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

interface ConversationChatViewProps {
  /** The unique identifier for the conversation to display. */
  conversationId: string;
  /** Optional: ID of a message to highlight initially. */
  highlightMessageId?: string | null;
  /**
   * The direction to assign to messages sent by the current user via the input box.
   * Defaults to 'out' (agent view). Set to 'in' for simulation view.
   * @default 'out'
   */
  userDirection?: "in" | "out";
}

/**
 * Component responsible for rendering the chat interface for a specific conversation.
 * Handles message fetching, display, sending, WebSocket updates, status changes,
 * and includes a 'scroll to bottom' button.
 * @param {ConversationChatViewProps} props - Component props.
 */
export function ConversationChatView({
  conversationId,
  highlightMessageId,
  userDirection = "out",
}: ConversationChatViewProps) {
  // --- Hooks and State ---
  const searchParams = useSearchParams();
  const highlightId = highlightMessageId ?? searchParams.get("highlight");
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
  // State for scroll-to-bottom button visibility
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

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
  } = useMessages(conversationId, highlightId);

  const { sendMessage, sending, error: sendError } = useSendMessage();

  // --- Fetch/Update Logic ---
  const fetchConversationData = useCallback(async () => {
    if (!conversationId) return;
    console.log(`Fetching details for conversation: ${conversationId}`);
    setLoadingDetails(true);
    setFetchDetailsError(null);
    try {
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
  }, [conversationId]);

  useEffect(() => {
    fetchConversationData();
  }, [fetchConversationData]);

  const handleUpdateStatus = useCallback(
    async (newStatus: ConversationStatusEnum) => {
      if (!conversationId) return;
      setIsUpdatingStatus(true);
      const previousDetails = conversationDetails;
      setConversationDetails((prev) =>
        prev ? { ...prev, status: newStatus } : null
      );
      try {
        await api.put(`/api/v1/conversations/${conversationId}/status`, {
          status: newStatus,
        });
        toast.success(`Conversa marcada como ${newStatus.toLowerCase()}!`);
      } catch (err) {
        console.error("Failed to update conversation status:", err);
        toast.error("Falha ao atualizar status da conversa.");
        setConversationDetails(previousDetails);
      } finally {
        setIsUpdatingStatus(false);
      }
    },
    [conversationId, conversationDetails]
  );

  // --- Send Message Logic ---
  const submitMessage = useCallback(async () => {
    if (!input.trim() || !conversationId) return;
    try {
      await sendMessage(input.trim(), conversationId, userDirection);
      setInput("");
      // Scroll to bottom after sending a message
      setTimeout(() => scrollToBottom("smooth"), 100); // Smooth scroll after send
    } catch (err: unknown) {
      console.error("Error sending message:", err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, conversationId, sendMessage, userDirection]); // Added scrollToBottom dependency later

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

  // --- Scroll Handlers ---
  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    if (messagesRef.current) {
      // Set flag to prevent scroll handler from interfering during auto-scroll
      setIsAutoScrolling(true);
      messagesRef.current.scrollTo({
        top: messagesRef.current.scrollHeight,
        behavior: behavior,
      });
      // Reset flag after scroll animation likely finishes
      // Use a timeout slightly longer than typical smooth scroll duration
      const scrollTimeout = behavior === "smooth" ? 300 : 50; // Adjust timeout if needed
      setTimeout(() => {
        setIsAutoScrolling(false);
        // Ensure button is hidden after auto-scrolling to bottom
        setShowScrollToBottom(false);
      }, scrollTimeout);
    }
  }, []); // Empty dependency array for scrollToBottom

  // Add submitMessage dependency after defining scrollToBottom
  useEffect(() => {
    // This effect is just to satisfy eslint exhaustive-deps for submitMessage needing scrollToBottom
  }, [scrollToBottom]);

  const handleScroll = useCallback(() => {
    const element = messagesRef.current;
    // Prevent checks during programmatic scroll or while loading
    if (!element || isAutoScrolling || loadingOlder || loadingNewer) return;

    const tolerance = 50; // Tolerance for loading more messages

    // Load older messages logic
    if (element.scrollTop <= tolerance && hasMoreOlder) {
      console.log("Requesting older messages");
      loadOlderMessages();
    }
    // Load newer messages logic (less common, but kept for completeness)
    if (
      element.scrollHeight - element.scrollTop - element.clientHeight <=
        tolerance &&
      hasMoreNewer
    ) {
      console.log("Requesting newer messages");
      loadNewerMessages();
    }

    // Check if the user is scrolled up *at all* from the absolute bottom
    const isAtBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight < 1; // Use 1px tolerance
    setShowScrollToBottom(!isAtBottom);
  }, [
    loadOlderMessages,
    loadNewerMessages,
    hasMoreOlder,
    hasMoreNewer,
    loadingOlder,
    loadingNewer,
    isAutoScrolling,
  ]);

  // Add/Remove scroll listener
  useEffect(() => {
    const element = messagesRef.current;
    if (!element) return;
    element.addEventListener("scroll", handleScroll);
    return () => element.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // Initial scroll and scroll on new messages
  useEffect(() => {
    if (!loadingOlder) {
      // Scroll immediately ('auto') on initial load or when new messages arrive
      scrollToBottom("auto");
    }
    // Depend on messages length to scroll when new messages are added
  }, [messages.length, loadingOlder, scrollToBottom]);

  // --- Loading Indicators ---
  const renderOlderMessagesLoadingIndicator = () => {
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
  if (fetchDetailsError && !loadingDetails) {
    return (
      <div className="p-4 text-center text-red-500">{fetchDetailsError}</div>
    );
  }

  return (
    // Added relative positioning to the main container
    <div className="flex flex-col w-full h-full bg-white dark:bg-neutral-900 relative">
      {/* Header Section */}
      <div className="w-full p-2 border-b flex justify-between items-center gap-2 sticky top-0 bg-background z-10">
        <span className="text-sm font-medium truncate">
          {loadingDetails ? (
            <Skeleton className="h-5 w-40" />
          ) : (
            `Conversa com ${
              conversationDetails?.contact?.name ||
              conversationDetails?.contact?.phone_number ||
              "Desconhecido"
            }`
          )}
        </span>
        <div
          className={cn(
            "flex items-center gap-2 ",
            userDirection === "out" ? "" : "hidden"
          )}
        >
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
            {" "}
            <Archive className="h-4 w-4 mr-1" /> Fechar{" "}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button // Único filho direto
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
                {" "}
                <Unlock className="mr-2 h-4 w-4" />{" "}
                <span>Reabrir (Pendente)</span>{" "}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() =>
                  handleUpdateStatus(ConversationStatusEnum.HUMAN_ACTIVE)
                }
                disabled={
                  isUpdatingStatus ||
                  loadingDetails ||
                  conversationDetails?.status ===
                    ConversationStatusEnum.HUMAN_ACTIVE
                }
              >
                {" "}
                <Play className="mr-2 h-4 w-4" /> <span>Marcar como Ativa</span>{" "}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Message List Area - Kept relative positioning */}
      <div
        className="w-full flex-grow overflow-y-auto px-4 mb-4 relative"
        ref={messagesRef}
      >
        {renderOlderMessagesLoadingIndicator()}
        <ChatWebSocketBridge
          conversationId={conversationId}
          onNewMessage={(message) => {
            setMessages((prev: Message[]) => {
              if (prev.some((m) => m.id === message.id)) return prev;
              return [...prev, message];
            });
          }}
        />
        <ChatMessageList>
          {loadingInitial && !messagesError && (
            <ChatBubble variant="received">
              <ChatBubbleAvatar src="" fallback="⏳" />
              <ChatBubbleMessage isLoading />
            </ChatBubble>
          )}
          {messagesError && !loadingInitial && <ConversationNotFound />}
          {!messagesError &&
            messages.map((message, index) => (
              <ChatMessage
                key={message.id || index}
                direction={message.direction}
                content={message.content}
                userDirection={userDirection}
              />
            ))}
        </ChatMessageList>
        {renderNewerMessagesLoadingIndicator()}
      </div>

      <div
        className={cn(
          "absolute bottom-50 left-1/2 transition-opacity duration-300 z-20",
          showScrollToBottom ? " opacity-100" : "opacity-0 pointer-events-none"
        )}
      >
        <Button
          variant="secondary"
          size="icon"
          className="rounded-full shadow-md h-10 w-10"
          onClick={() => scrollToBottom("smooth")}
          aria-label="Rolar para baixo"
        >
          <ArrowDown className="h-5 w-5" />
        </Button>
      </div>

      {/* Input Box Area */}
      <div className="w-full flex flex-col px-4 pb-4 pt-4 bg-background border-t">
        <ChatInputBox
          value={input}
          onChange={handleInputChange}
          onSubmit={handleSend}
          onKeyDown={handleKeyDown}
          disabled={sending || !input.trim()}
        />
        {sendError && (
          <p className="text-red-500 text-xs text-center mt-2">{sendError}</p>
        )}
      </div>
    </div>
  );
}

export default ConversationChatView;
