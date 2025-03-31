import { useEffect, useRef } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';
import type { ConversationSocketEvent } from '@/types/conversation';

interface ConversationSocketEvents {
  onNewConversation?: (data: ConversationSocketEvent['payload']) => void;
  onConversationUpdate?: (data: ConversationSocketEvent['payload']) => void;
}

/**
 * Hook to manage WebSocket connection for conversation-related events with reconnection.
 *
 * Connects to `/ws/accounts/{socketIdentifier}/conversations` and dispatches events:
 * - `new_conversation`
 * - `conversation_updated`
 *
 * @param socketIdentifier - The identifier needed to establish the WebSocket connection
 *                           (e.g., internal account ID).
 * @param events - Object with optional callbacks for event types.
 */
export function useConversationSocket(socketIdentifier: string, events: ConversationSocketEvents) {
  const socketRef = useRef<ReconnectingWebSocket | null>(null);
  const { onNewConversation, onConversationUpdate } = events;

  useEffect(() => {
    if (!socketIdentifier) {
      console.warn('useConversationSocket: socketIdentifier is not provided.');
      return;
    }

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL;
    if (!wsUrl) {
      console.error('useConversationSocket: NEXT_PUBLIC_WS_URL is not defined.');
      return;
    }
    
    // Converte a URL para o esquema ws:// ou wss://, se necessário
    let socketUrl = wsUrl;
    if (!socketUrl.startsWith('ws://') && !socketUrl.startsWith('wss://')) {
      socketUrl = socketUrl.replace(/^http/, 'ws');
    }

    // Monta a URL de conexão para a lista de conversas
    const url = `${socketUrl}/ws/accounts/${socketIdentifier}/conversations`;
    console.log('Connecting to WebSocket URL:', url);

    // Define as opções de reconexão
    const options = {
      reconnectInterval: 2000,
      connectionTimeout: 4000,
    };

    // Cria a instância do ReconnectingWebSocket
    const rws = new ReconnectingWebSocket(url, [], options);
    socketRef.current = rws;

    // Captura o evento de conexão
    rws.onopen = () => {
      console.debug('[ReconnectingWebSocket] Connected to conversation channel (onopen).');
    };
    rws.addEventListener('open', () => {
      console.debug('[ReconnectingWebSocket] Connected to conversation channel (addEventListener).');
    });

    rws.addEventListener('message', (event: MessageEvent) => {
      console.debug('[ReconnectingWebSocket] Message received:', event.data);
      try {
        const message: ConversationSocketEvent = JSON.parse(event.data);
        const { type, payload } = message;
        if (type === 'new_conversation' && onNewConversation) {
          // Se payload for undefined, usa o objeto completo (message) como fallback
          const conversation = payload ?? message;
          if (!conversation.id) {
            console.warn('[ReconnectingWebSocket] new_conversation conversation object is invalid:', conversation);
            return;
          }
          console.debug('[ReconnectingWebSocket] new_conversation event:', conversation);
          onNewConversation(conversation);
        } else if (type === 'conversation_updated' && onConversationUpdate) {
          if (!payload || !payload.id) {
            console.warn('[ReconnectingWebSocket] conversation_updated payload is invalid:', payload);
            return;
          }
          console.debug('[ReconnectingWebSocket] conversation_updated event:', payload);
          onConversationUpdate(payload);
        } else {
          console.warn('[ReconnectingWebSocket] Unhandled message type:', type);
        }
      } catch (err) {
        console.error('[ReconnectingWebSocket] Failed to parse message:', err);
      }
    });

    rws.addEventListener('error', (error) => {
      console.error('[ReconnectingWebSocket] Error:', error);
      console.error('WebSocket readyState:', rws.readyState);
    });

    rws.addEventListener('close', () => {
      console.debug('[ReconnectingWebSocket] Disconnected from conversation channel.');
    });

    return () => {
      console.debug('[ReconnectingWebSocket] Closing connection.');
      rws.close();
    };
  }, [socketIdentifier, onNewConversation, onConversationUpdate]);
}
