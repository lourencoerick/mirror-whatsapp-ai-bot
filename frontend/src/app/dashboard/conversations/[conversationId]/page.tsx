'use client';

import {
  ChatBubble,
  ChatBubbleAvatar,
  ChatBubbleMessage,
} from '@/components/ui/chat/chat-bubble';
import { ChatMessageList } from '@/components/ui/chat/chat-message-list';
import { ChatInput } from '@/components/ui/chat/chat-input';
import { Button } from '@/components/ui/button';
import { CornerDownLeft, Mic, Paperclip } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useRef, useEffect, useState } from 'react';
import { useMessages } from '@/hooks/use-messages';

const ChatPage = () => {
  const { conversationId } = useParams();
  const { messages, loading, error } = useMessages(conversationId as string);
  const [input, setInput] = useState('');
  const messagesRef = useRef<HTMLDivElement>(null);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleSend = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    // future: send message to backend
    console.log('Sending message:', input);
    setInput('');
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
            <ChatBubble
              key={index}
              variant={message.message_type === 'out' ? 'sent' : 'received'}
            >
              <ChatBubbleAvatar
                src=""
                fallback={message.message_type === 'out' ? '👤' : '🤖'}
              />
              <ChatBubbleMessage>{`${message.content}`}</ChatBubbleMessage>
            </ChatBubble>
          ))}
        </ChatMessageList>
      </div>

      <div className="w-full px-4 pb-4">
        <form
          onSubmit={handleSend}
          className="relative rounded-lg border bg-background focus-within:ring-1 focus-within:ring-ring"
        >
          <ChatInput
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Digite sua mensagem..."
            className="rounded-lg bg-background border-0 shadow-none focus-visible:ring-0"
          />
          <div className="flex items-center p-3 pt-0">
            <Button variant="ghost" size="icon">
              <Paperclip className="size-4" />
              <span className="sr-only">Anexar arquivo</span>
            </Button>

            <Button variant="ghost" size="icon">
              <Mic className="size-4" />
              <span className="sr-only">Usar microfone</span>
            </Button>

            <Button
              type="submit"
              disabled={!input}
              size="sm"
              className="ml-auto gap-1.5"
            >
              Enviar <CornerDownLeft className="size-3.5" />
            </Button>
          </div>
        </form>
      </div>
    </main>
  );
};

export default ChatPage;
