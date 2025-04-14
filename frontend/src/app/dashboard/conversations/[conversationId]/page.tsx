'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  ChatBubble,
  ChatBubbleAvatar,
  ChatBubbleMessage,
} from '@/components/ui/chat/chat-bubble';
import { ChatMessageList } from '@/components/ui/chat/chat-message-list';
import { ChatMessage } from "@/components/ui/chat/chat-message";
import { ChatInputBox } from "@/components/ui/chat/chat-input-box";
import { ChatWebSocketBridge } from '@/components/ui/chat/chat-websocket-bridge';
import { useMessages } from '@/hooks/use-messages';
import { useSendMessage } from "@/hooks/use-send-message";
import { useLayoutContext } from '@/contexts/layout-context';
import { Message } from '@/types/message';
import { Conversation, ConversationStatusEnum } from '@/types/conversation';
import ConversationNotFound from "@/components/ui/conversation/conversation-notfound";
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Archive, MoreVertical, Unlock, Play, ArrowLeft } from 'lucide-react';
import api from '@/lib/api';
import { toast } from 'sonner';
import { Skeleton } from "@/components/ui/skeleton";

const ChatPage = () => {
  // Starting hooks and states
  const { conversationId } = useParams() as { conversationId: string };
  const searchParams = useSearchParams();
  const highlightId = searchParams.get('highlight');
  const { setPageTitle } = useLayoutContext();
  const messagesRef = useRef<HTMLDivElement>(null);

  const [input, setInput] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [isAutoScrolling, setIsAutoScrolling] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [conversationDetails, setConversationDetails] = useState<Conversation | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(true);
  const [fetchDetailsError, setFetchDetailsError] = useState<string | null>(null);

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

  useEffect(() => {
    setPageTitle(
      <div className="flex items-center gap-2">
        <Link href="/dashboard/conversations" className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground" aria-label="Voltar para Caixas de Entrada">
          <ArrowLeft className="h-4 w-4" />
          <span className="font-semibold">Conversas</span>
        </Link>
        <span className="text-sm text-muted-foreground">/</span>
        <span className="font-semibold">Conversa</span>
      </div>
    );
  }, [setPageTitle]);

  // Fetch the data of the conversation
  const fetchConversationData = useCallback(async () => {
    if (!conversationId) return;
    console.log(`Fetching details for conversation: ${conversationId}`);
    setLoadingDetails(true);
    setFetchDetailsError(null);
    try {
      const response = await api.get<Conversation>(`/api/v1/conversations/${conversationId}`);
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

  // Updating the status of conversation
  const handleUpdateStatus = useCallback(async (newStatus: ConversationStatusEnum) => {
    if (!conversationId) return;
    setIsUpdatingStatus(true);
    const previousDetails = conversationDetails;
    setConversationDetails(prev => prev ? { ...prev, status: newStatus } : null);
    try {
      await api.put(`/api/v1/conversations/${conversationId}/status`, { status: newStatus });
      toast.success(`Conversa marcada como ${newStatus.toLowerCase()}!`);
    } catch (err) {
      console.error("Failed to update conversation status:", err);
      toast.error("Falha ao atualizar status da conversa.");
      setConversationDetails(previousDetails);
    } finally {
      setIsUpdatingStatus(false);
    }
  }, [conversationId, conversationDetails]);

  // Handlers of input and  message sender 
  const submitMessage = async () => {
    if (!input.trim() || !conversationId) return;
    try {
      await sendMessage(input.trim(), conversationId);
      setInput('');
    } catch (err: unknown) {
      console.error('Error sending message:', err);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => setInput(e.target.value);

  const handleSend = useCallback(async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    await submitMessage()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, conversationId, submitMessage]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitMessage();
    }
  };

  // Scroll Handlers 
  const scrollToBottom = useCallback(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, []);

  const handleScroll = useCallback(() => {
    const element = messagesRef.current;
    if (!element || loadingOlder || loadingNewer || isAutoScrolling) return;
    const tolerance = 50;
    if (element.scrollTop <= tolerance && hasMoreOlder) {
      console.log("Requesting older messages");
      loadOlderMessages();
    }
    if (element.scrollHeight - element.scrollTop - element.clientHeight <= tolerance && hasMoreNewer) {
      console.log("Requesting newer messages");
      loadNewerMessages();
    }
  }, [loadOlderMessages, loadNewerMessages, hasMoreOlder, hasMoreNewer, loadingOlder, loadingNewer, isAutoScrolling]);

  useEffect(() => {
    const element = messagesRef.current;
    if (!element) return;
    element.addEventListener('scroll', handleScroll);
    return () => element.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  useEffect(() => {
    if (!loadingOlder) {
      setTimeout(scrollToBottom, 100);
    }
  }, [messages, loadingOlder, scrollToBottom]);

  // Loading indicators
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

  // Rendering
  if (fetchDetailsError && !loadingDetails) {
    return <div className="p-4 text-center text-red-500">{fetchDetailsError}</div>;
  }

  return (
    <main className="flex flex-col w-full h-full bg-white dark:bg-neutral-900">
      <div className="w-full p-2 border-b flex justify-between items-center gap-2 sticky top-0 bg-background z-10">
        <span className="text-sm font-medium truncate">
          {loadingDetails ? (
            <Skeleton className="h-5 w-40" />
          ) : (
            `Conversa com ${conversationDetails?.contact?.name || conversationDetails?.contact?.phone_number || 'Desconhecido'}`
          )}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleUpdateStatus(ConversationStatusEnum.CLOSED)}
            disabled={isUpdatingStatus || loadingDetails || conversationDetails?.status === ConversationStatusEnum.CLOSED}
            aria-label="Fechar Conversa"
          >
            <Archive className="h-4 w-4 mr-1" />
            Fechar
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" disabled={isUpdatingStatus || loadingDetails} aria-label="Mais opções">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() => handleUpdateStatus(ConversationStatusEnum.PENDING)}
                disabled={isUpdatingStatus || loadingDetails || conversationDetails?.status === ConversationStatusEnum.PENDING}
              >
                <Unlock className="mr-2 h-4 w-4" />
                <span>Reabrir (Pendente)</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => handleUpdateStatus(ConversationStatusEnum.HUMAN_ACTIVE)}
                disabled={isUpdatingStatus || loadingDetails || conversationDetails?.status === ConversationStatusEnum.HUMAN_ACTIVE}
              >
                <Play className="mr-2 h-4 w-4" />
                <span>Marcar como Ativa</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="w-full flex-grow overflow-y-auto px-4" ref={messagesRef}>
        {renderOlderMessagesLoadingIndicator()}
        <ChatWebSocketBridge
          conversationId={conversationId}
          onNewMessage={(message) => {
            setMessages((prev: Message[]) => {
              if (prev.some(m => m.id === message.id)) return prev;
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
          {!messagesError && messages.map((message, index) => (
            <ChatMessage
              key={message.id || index}
              direction={message.direction}
              content={message.content}
            />
          ))}
        </ChatMessageList>
        {renderNewerMessagesLoadingIndicator()}
      </div>

      <div className="w-full px-4 pb-4 pt-4 bg-background">
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
    </main>
  );
};

export default ChatPage;
