'use client';

import {
  ChatBubble,
  ChatBubbleAvatar,
  ChatBubbleMessage,
} from '@/components/ui/chat/chat-bubble';
import { ChatMessageList } from '@/components/ui/chat/chat-message-list';
import { useParams } from 'next/navigation';
import { useRef, useEffect, useState } from 'react';
import { useMessages } from '@/hooks/use-messages';
import { useSendMessage } from "@/hooks/use-send-message";


import { ChatMessage } from "@/components/ui/chat/chat-message";
import { ChatInputBox } from "@/components/ui/chat/chat-input-box";

const ChatPage = () => {
  const { conversationId } = useParams();
  const { messages, loading, error } = useMessages(conversationId as string);
  const { sendMessage, sending, error: sendError } = useSendMessage();
  const [input, setInput] = useState('');
  const messagesRef = useRef<HTMLDivElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleSend = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim()) return;

    try {
      await sendMessage(input.trim(), conversationId as string);
      setInput('');
    } catch (err) {
      console.error('Error trying to the send a message:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e as any);
    }
  };

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <main className="flex w-full max-w-3xl flex-col items-center mx-auto">
      <div className="flex-1 w-full overflow-y-auto py-6" ref={messagesRef}>
        <ChatMessageList>
          {loading && (
            <ChatBubble variant="received">
              <ChatBubbleAvatar src="" fallback="🤖" />
              <ChatBubbleMessage isLoading />
            </ChatBubble>
          )}

          {error && (
            <div className="text-red-500 p-4">Erro ao carregar mensagens.</div>
          )}

          {messages.map((message, index) => (
            <ChatMessage
              key={index}
              direction={message.message_type}
              content={message.content}
            />
          ))}
        </ChatMessageList>
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
