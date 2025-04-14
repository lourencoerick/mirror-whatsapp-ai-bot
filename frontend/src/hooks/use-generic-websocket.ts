/* eslint-disable react-hooks/exhaustive-deps */
import { useEffect, useRef, useCallback } from 'react';
import ReconnectingWebSocket, { Options } from 'reconnecting-websocket';

/**
 * Props for the useWebSocket hook.
 */
interface UseWebSocketProps {
  url: string | null | undefined;
  /** Optional configuration options for ReconnectingWebSocket. */
  options?: Options;
  /** Callback function triggered when the connection is successfully opened. */
  onOpen?: (event: Event) => void;
  /** 
   * Callback function triggered when a message is received from the server.
   * The hook consumer is responsible for parsing the message data (event.data).
   */
  onMessage: (event: MessageEvent) => void;
  /** Callback function triggered when a WebSocket error occurs. */
  onError?: (event: Event) => void;
  /** Callback function triggered when the connection is closed. */
  onClose?: (event: CloseEvent) => void;
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
  
  // Memoize the callbacks to prevent unnecessary effect runs if they are defined inline
  const memoizedOnOpen = useCallback(onOpen || (() => {}), [onOpen]);
  const memoizedOnMessage = useCallback(onMessage, [onMessage]);
  const memoizedOnError = useCallback(onError || (() => {}), [onError]);
  const memoizedOnClose = useCallback(onClose || (() => {}), [onClose]);

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

    // Default options for ReconnectingWebSocket if none are provided
    const defaultOptions: Options = {
      connectionTimeout: 10000, // ms
      maxRetries: 10, // Number of attempts before giving up
    };

    const connectionOptions = { ...defaultOptions, ...options };

    // Create a new ReconnectingWebSocket instance
    const rws = new ReconnectingWebSocket(url, [], connectionOptions);
    socketRef.current = rws;

    // Attach event listeners using the memoized callbacks
    const handleOpen = (event: Event) => {
      console.debug(`[useWebSocket] Connected to ${url}`);
      memoizedOnOpen(event);
    };

    const handleMessage = (event: MessageEvent) => {
      console.debug(`[useWebSocket] Message received from ${url}:`, event.data);
      memoizedOnMessage(event);
    };

    const handleError = (event: Event) => {
      console.error(`[useWebSocket] Error on connection to ${url}:`, event);
      memoizedOnError(event);
    };

    const handleClose = (event: CloseEvent) => {
      console.debug(`[useWebSocket] Disconnected from ${url}. Code: ${event.code}, Reason: ${event.reason}`);
      // Ensure the ref is cleared on close, especially if not reconnecting indefinitely
      if (socketRef.current === rws) { 
          // Check if it's the same instance, might have been replaced if url/enabled changed quickly
          // socketRef.current = null; // Let ReconnectingWebSocket manage its internal state for retries
      }
      memoizedOnClose(event);
    };

    rws.addEventListener('open', handleOpen);
    rws.addEventListener('message', handleMessage);
    rws.addEventListener('error', handleError);
    rws.addEventListener('close', handleClose);

    // Cleanup function: close the WebSocket connection when the component unmounts
    // or when the dependencies (url, enabled, options, callbacks) change.
    return () => {
      if (rws) {
        console.debug(`[useWebSocket] Cleaning up connection to ${url}`);
        // Remove listeners to prevent memory leaks and potential calls on stale closures
        rws.removeEventListener('open', handleOpen);
        rws.removeEventListener('message', handleMessage);
        rws.removeEventListener('error', handleError);
        rws.removeEventListener('close', handleClose);
        
        // Close the connection
        rws.close();
        // Clear the ref only if this specific instance is being cleaned up
        if (socketRef.current === rws) {
            socketRef.current = null;
        }
      }
    };

  }, [url, enabled, options, memoizedOnOpen, memoizedOnMessage, memoizedOnError, memoizedOnClose]); 

}