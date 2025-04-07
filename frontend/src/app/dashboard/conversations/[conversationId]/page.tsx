'use client';

import {
  ChatBubble,
  ChatBubbleAvatar,
  ChatBubbleMessage,
} from '@/components/ui/chat/chat-bubble';
import { ChatMessageList } from '@/components/ui/chat/chat-message-list';
import { useParams, useSearchParams } from 'next/navigation';
import { useRef, useEffect, useState, useCallback } from 'react';
import { useMessages } from '@/hooks/use-messages';
import { useSendMessage } from "@/hooks/use-send-message";
import { ChatMessage } from "@/components/ui/chat/chat-message";
import { ChatInputBox } from "@/components/ui/chat/chat-input-box";
import { ChatWebSocketBridge } from '@/components/ui/chat/chat-websocket-bridge';
import { Message } from '@/types/message';
import { useLayoutContext } from '@/contexts/layout-context';



import Link from 'next/link';
import { MessageSquareOff, LockKeyhole } from 'lucide-react'; // Using two icons for illustration
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import ConversationNotFound from "@/components/ui/conversation/unavailable-conversation"

const ChatPage = () => {



  const { conversationId } = useParams() as { conversationId: string };
  const searchParams = useSearchParams();
  const highlightId = searchParams.get('highlight');

  const { setPageTitle } = useLayoutContext();
  useEffect(() => {
    setPageTitle(`Conversa ID: ${conversationId}`);
  }, [setPageTitle, conversationId]);

  const {
    messages,
    setMessages,
    loadingInitial,
    loadingOlder,
    loadingNewer,
    error,
    hasMoreOlder,
    hasMoreNewer,
    loadOlderMessages,
    loadNewerMessages,
  } = useMessages(conversationId as string, highlightId as string | null);
  const { sendMessage, sending, error: sendError } = useSendMessage();
  const [input, setInput] = useState('');
  const messagesRef = useRef<HTMLDivElement>(null);
  const [isAutoScrolling, setIsAutoScrolling] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const scrollToBottom = useCallback(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, []);

  const handleSend = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim()) return;

    try {
      await sendMessage(input.trim(), conversationId as string);
      setInput('');
      scrollToBottom(); // Auto-scroll after sending
    } catch (err) {
      console.error('Error trying to send a message:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e as any);
    }
  };

  const handleScroll = useCallback(() => {
    const element = messagesRef.current;
    if (!element || loadingOlder || loadingNewer || isAutoScrolling) return;

    const tolerance = 50;
    if (element.scrollTop <= tolerance && hasMoreOlder) {
      console.log("loadOlderMessages")
      loadOlderMessages();
    }

    if (element.scrollHeight - element.scrollTop - element.clientHeight <= tolerance && hasMoreNewer) {
      console.log("loadNewerMessages")
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
    const element = messagesRef.current;
    if (!element || loadingInitial) return;

    const nearBottom = element.scrollHeight - element.scrollTop - element.clientHeight <= 100;
    const nearTop = element.scrollTop <= 100;

    if (!nearBottom && !nearTop) {
      setIsAutoScrolling(true);
      element.scrollTop = element.scrollHeight;
      setIsAutoScrolling(false);
    }
  }, [messages, loadingInitial]);

  const renderOlderMessagesLoadingIndicator = () => {
    if (loadingOlder) {
      return (
        <div className="text-center py-2">
          <ChatBubble variant="received">
            <ChatBubbleAvatar src="" fallback="🤖" />
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
            <ChatBubbleAvatar src="" fallback="🤖" />
            <ChatBubbleMessage isLoading />
          </ChatBubble>
        </div>
      );
    }
    return null;
  };


  return (
    <main className="flex flex-col w-full max-w-3xl  items-center mx-auto h-full">
      <div
        className="w-full h-full overflow-y-auto"
        ref={messagesRef}
      >
        {renderOlderMessagesLoadingIndicator()}

        <ChatWebSocketBridge
          conversationId={conversationId}
          onNewMessage={(message) => {
            setMessages((prev: Message[]) => [...prev, message]);
            scrollToBottom();
          }}
        />
        <ChatMessageList>
          {loadingInitial && (
            <ChatBubble variant="received">
              <ChatBubbleAvatar src="" fallback="🤖" />
              <ChatBubbleMessage isLoading />
            </ChatBubble>
          )}

          {error && (
            <ConversationNotFound />
          )}

          {messages.map((message, index) => (

            <ChatMessage
              key={index}
              direction={message.direction}
              content={message.content}
            />
          ))}
        </ChatMessageList>
        {renderNewerMessagesLoadingIndicator()}
      </div>

      <div className="w-full px-4 pb-4">
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