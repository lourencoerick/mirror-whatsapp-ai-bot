'use client';

import { useEffect, useRef } from 'react';
import ReconnectingWebSocket from 'reconnecting-websocket';
import { MessageSocketEvent } from "@/types/message"

interface Props {
  conversationId: string;
  onNewMessage: (msg: MessageSocketEvent['payload']) => void;
}

export function ChatWebSocketBridge({ conversationId, onNewMessage }: Props) {
  const wsRef = useRef<ReconnectingWebSocket | null>(null);
  const onNewMessageRef = useRef(onNewMessage);

  useEffect(() => {
    onNewMessageRef.current = onNewMessage;
  }, [onNewMessage]);

  useEffect(() => {
    const url = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/ws/conversations/${conversationId}`;
    const ws = new ReconnectingWebSocket(url);
    wsRef.current = ws;

    console.log("[WebSocket] Connecting to:", url);

    ws.addEventListener("open", () => {
      console.log(`[WebSocket] Connected to conversation ${conversationId}`);
    });

    ws.addEventListener("message", (event: MessageEvent) => {
      try {
        const data: MessageSocketEvent = JSON.parse(event.data);
        if (data.type === "new_message" || data.type === "incoming_message") {
          onNewMessageRef.current(data.payload);
          console.log(`[WebSocket]: payload recieved: ${data.payload.direction}`)
        }
      } catch (err) {
        console.warn("[WebSocket] Invalid message:", err);
      }
    });

    ws.addEventListener("error", (err) => {
      console.error("[WebSocket] Error", err);
    });

    ws.addEventListener("close", () => {
      console.log(`[WebSocket] Disconnected from conversation ${conversationId}`);
    });

    return () => {
      ws.close();
    };
  }, [conversationId]);

  return null;
}
