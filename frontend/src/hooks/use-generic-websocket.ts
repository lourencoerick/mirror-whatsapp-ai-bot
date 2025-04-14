/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable react-hooks/exhaustive-deps */
import { useEffect, useRef, useCallback } from 'react';
// Import specific event types from the library itself
import ReconnectingWebSocket, { 
    Options, 
    Event as RwsEvent,      // Import the library's Event type
    CloseEvent as RwsCloseEvent // Import the library's CloseEvent type
} from 'reconnecting-websocket';
// We will use the global DOM MessageEvent for onMessage/handleMessage

/**
 * Props for the useWebSocket hook.
 */
interface UseWebSocketProps {
  url: string | null | undefined;
  /** Optional configuration options for ReconnectingWebSocket. */
  options?: Options;
  /** Callback function triggered when the connection is successfully opened. Uses the library's Event type. */
  onOpen?: (event: RwsEvent) => void; // Use library's Event
  /**
   * Callback function triggered when a message is received from the server.
   * Uses the standard DOM MessageEvent type.
   */
  onMessage: (event: MessageEvent) => void; // Use standard DOM MessageEvent
  /** Callback function triggered when a WebSocket error occurs. Uses the library's Event type. */
  onError?: (event: RwsEvent) => void; // Use library's Event
  /** Callback function triggered when the connection is closed. Uses the library's CloseEvent type. */
  onClose?: (event: RwsCloseEvent) => void; // Use library's CloseEvent
  /** Set to false to disable the WebSocket connection. Defaults to true. */
  enabled?: boolean;
}

/**
 * A generic React hook to manage a WebSocket connection using ReconnectingWebSocket.
 *
 * Handles connection, reconnection, and cleanup automatically.
 * Allows specifying callbacks for open, message, error, and close events.
 *
 * @param props - The configuration properties for the WebSocket connection.
 * @returns void - This hook does not return any value but manages the WebSocket lifecycle.
 */
export function useWebSocket({
  url,
  options,
  onOpen,
  onMessage,
  onError,
  onClose,
  enabled = true,
}: UseWebSocketProps): void {
  const socketRef = useRef<ReconnectingWebSocket | null>(null);

  // Memoize the callbacks, ensuring default functions match the expected signatures
  const memoizedOnOpen = useCallback(onOpen || ((_event: RwsEvent) => {}), [onOpen]);
  const memoizedOnMessage = useCallback(onMessage, [onMessage]);
  const memoizedOnError = useCallback(onError || ((_event: RwsEvent) => {}), [onError]);
  const memoizedOnClose = useCallback(onClose || ((_event: RwsCloseEvent) => {}), [onClose]);

  useEffect(() => {
    if (!enabled || !url) {
      if (socketRef.current) {
        console.debug('[useWebSocket] Disabled or URL missing. Closing existing connection.');
        socketRef.current.close();
        socketRef.current = null;
      }
      return;
    }

    if (!url.startsWith('ws://') && !url.startsWith('wss://')) {
        console.warn(`[useWebSocket] URL "${url}" does not start with ws:// or wss://. Attempting connection anyway.`);
    }

    console.debug(`[useWebSocket] Attempting to connect to: ${url}`);

    const defaultOptions: Options = {
      connectionTimeout: 10000,
      maxRetries: 10,
    };

    const connectionOptions = { ...defaultOptions, ...options };

    const rws = new ReconnectingWebSocket(url, [], connectionOptions);
    socketRef.current = rws;

    // Attach event listeners using the types from the library or global DOM where appropriate
    const handleOpen = (event: RwsEvent) => { // Use library's Event type
      console.debug(`[useWebSocket] Connected to ${url}`);
      memoizedOnOpen(event);
    };

    const handleMessage = (event: MessageEvent) => { // Use global DOM MessageEvent
      console.debug(`[useWebSocket] Message received from ${url}:`, event.data);
      memoizedOnMessage(event);
    };

    const handleError = (event: RwsEvent) => { // Use library's Event type
      console.error(`[useWebSocket] Error on connection to ${url}:`, event);
      memoizedOnError(event);
    };

    const handleClose = (event: RwsCloseEvent) => { // Use library's CloseEvent type
      console.debug(`[useWebSocket] Disconnected from ${url}. Code: ${event.code}, Reason: ${event.reason}`);
      memoizedOnClose(event);
    };

    // IMPORTANT: Type assertion might be needed if TS still complains
    // This tells TypeScript to trust us that the handler is compatible.
    // Use this as a last resort if the type imports don't fully resolve it.
    // rws.addEventListener('open', handleOpen as EventListener); 
    // rws.addEventListener('message', handleMessage as EventListener);
    // rws.addEventListener('error', handleError as EventListener);
    // rws.addEventListener('close', handleClose as EventListener);

    // Prefer direct type matching if possible:
    rws.addEventListener('open', handleOpen);
    rws.addEventListener('message', handleMessage); // Still using global MessageEvent here
    rws.addEventListener('error', handleError);
    rws.addEventListener('close', handleClose);


    return () => {
      if (rws) {
        console.debug(`[useWebSocket] Cleaning up connection to ${url}`);
        // Use the same handler references for removal
        rws.removeEventListener('open', handleOpen);
        rws.removeEventListener('message', handleMessage);
        rws.removeEventListener('error', handleError);
        rws.removeEventListener('close', handleClose);
        rws.close();
        if (socketRef.current === rws) {
            socketRef.current = null;
        }
      }
    };

  }, [url, enabled, options, memoizedOnOpen, memoizedOnMessage, memoizedOnError, memoizedOnClose]);

}