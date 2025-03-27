'use client';

import { useEffect, useRef } from 'react';

interface WebSocketMessage {
  type: string;
  message: any;
}

interface Props {
  conversationId: number;
  onNewMessage: (msg: WebSocketMessage['message']) => void;
}

export function ChatWebSocketBridge({ conversationId, onNewMessage }: Props) {
  const wsRef = useRef<WebSocket | null>(null);
  const onNewMessageRef = useRef(onNewMessage);

  useEffect(() => {
    onNewMessageRef.current = onNewMessage;
  }, [onNewMessage]);

  useEffect(() => {
    const url = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/ws/conversations/${conversationId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    console.log("[WebSocket] Connecting to:", url);

    ws.onopen = () => {
      console.log(`[WebSocket] Connected to conversation ${conversationId}`);
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data: WebSocketMessage = JSON.parse(event.data);
        if (data.type === "new_message" || data.type === "incoming_message") {
          onNewMessageRef.current(data.message);
        }
      } catch (err) {
        console.warn("[WebSocket] Invalid message:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("[WebSocket] Error", err);
    };

    ws.onclose = () => {
      console.log(`[WebSocket] Disconnected from conversation ${conversationId}`);
    };

    return () => {
      ws.close();
    };
  }, [conversationId]);

  return null;
}
