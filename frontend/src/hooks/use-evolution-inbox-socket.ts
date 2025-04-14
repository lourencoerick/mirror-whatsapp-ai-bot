/* eslint-disable @typescript-eslint/no-unused-vars */
import { useState, useEffect, useMemo, useCallback } from 'react';
import { useWebSocket } from './use-generic-websocket';
import { Event as RwsEvent, CloseEvent as RwsCloseEvent } from 'reconnecting-websocket';
import { toast } from 'sonner';

interface InstanceStatusUpdate {
  instane_id: string;
  status: 'CONNECTED' | 'DISCONNECTED' | 'TIMEOUT' | 'ERROR' | string;
}

interface InstanceStatusEvent {
  type: "connection.update";
  payload: InstanceStatusUpdate;
}

interface InboxSocketEvents {
  onConnected?: () => void;
  onTimeout?: () => void;
  onInstanceError?: (message?: string) => void;
  onDisconnected?: () => void;
  onMessage?: (message: InstanceStatusEvent) => void;
  onOpen?: (event: RwsEvent) => void; // Use library's Event type
  onClose?: (event: RwsCloseEvent) => void; // Use library's CloseEvent type
  onSocketError?: (event: RwsEvent) => void; // Use library's Event type for errors
}

interface UseInboxSocketProps extends InboxSocketEvents {
  instanceId: string | null | undefined;
}

/**
 * Hook para gerenciar a conexão WebSocket de status de instância.
 * A URL é construída com o token obtido assincronamente do Clerk.
 */
export function useInboxSocket({
  instanceId,
  onConnected,
  onTimeout,
  onInstanceError,
  onDisconnected,
  onMessage,
  onOpen,
  onClose,
  onSocketError,
}: UseInboxSocketProps): void {


  const [wsUrl, setWsUrl] = useState<string | null>(null);

  // Busca o token e constrói a URL do WebSocket com o token na query string
  useEffect(() => {
    async function updateUrl() {
      if (!instanceId) {
        setWsUrl(null);
        return;
      }
      try {
        const baseWsUrl = process.env.NEXT_PUBLIC_WS_URL;
        if (!baseWsUrl) {
          console.error('[useInboxSocket] NEXT_PUBLIC_WS_URL is not defined.');
          setWsUrl(null);
          return;
        }
        const socketUrl = baseWsUrl.startsWith('ws://') || baseWsUrl.startsWith('wss://')
          ? baseWsUrl
          : baseWsUrl.replace(/^http/, 'ws');
        // Adiciona o token na URL como parâmetro
        const fullUrl = `${socketUrl}/ws/instances/${instanceId}/status`;
        setWsUrl(fullUrl);
      } catch (error) {
        console.error('[useInboxSocket] Failed to get token:', error);
        setWsUrl(null);
      }
    }
    updateUrl();
  }, [instanceId]);

  // Memoiza os callbacks para garantir referências estáveis
  const memoizedCallbacks = useMemo(() => ({
    onConnected: onConnected || (() => {}),
    onTimeout: onTimeout || (() => {}),
    onInstanceError: onInstanceError || (() => {}),
    onDisconnected: onDisconnected || (() => {}),
    onMessage: onMessage || (() => {}),
    onOpen: onOpen || ((_event: RwsEvent) => {}), // Default matches RwsEvent
    onClose: onClose || ((_event: RwsCloseEvent) => {}), // Default matches RwsCloseEvent
    onError: onSocketError || ((_event: RwsEvent) => {}), // Default matches RwsEvent (for onSocketError)
  }), [onConnected, onTimeout, onInstanceError, onDisconnected, onMessage, onOpen, onClose, onSocketError]);

  // Manipula as mensagens recebidas do WebSocket
  const handleMessage = useCallback((event: MessageEvent) => {
    let message: InstanceStatusEvent;
    try {
      // Assume que event.data é uma string JSON
      message = JSON.parse(event.data);
      if (!message || typeof message.payload.status !== 'string') {
        console.warn('[useInboxSocket] Received invalid message structure:', message);
        return;
      }
      memoizedCallbacks.onMessage(message);

      switch (message.payload.status) {
        case 'CONNECTED':
          console.info(`[useInboxSocket] Received CONNECTED status for instance ${instanceId}.`);
          toast.success("WhatsApp conectado com sucesso!");
          memoizedCallbacks.onConnected();
          break;
        case 'DISCONNECTED':
          console.info(`[useInboxSocket] Received DISCONNECTED status for instance ${instanceId}.`);
          memoizedCallbacks.onDisconnected();
          break;
        case 'TIMEOUT':
          console.warn(`[useInboxSocket] Received TIMEOUT status for instance ${instanceId}.`);
          toast.warning("Tempo esgotado para escanear o QR code.");
          memoizedCallbacks.onTimeout();
          break;
        case 'ERROR':
          console.error(`[useInboxSocket] Received ERROR status for instance ${instanceId}:`, message);
          toast.error("Ocorreu um erro na instância.");
          memoizedCallbacks.onInstanceError();
          break;
        default:
          console.warn(`[useInboxSocket] Received unhandled status: ${message.payload.status}`);
          break;
      }
    } catch (err) {
      console.error('[useInboxSocket] Failed to parse message or handle status:', err, 'Raw data:', event.data);
      toast.error("Erro ao processar mensagem do servidor.");
    }
  }, [instanceId, memoizedCallbacks]);

  // Utiliza o hook genérico de WebSocket passando a URL atualizada e os callbacks
  useWebSocket({
    url: wsUrl,
    onMessage: handleMessage,
    onOpen: memoizedCallbacks.onOpen,
    onError: memoizedCallbacks.onError,
    onClose: memoizedCallbacks.onClose,
    enabled: !!wsUrl,
  });
}
