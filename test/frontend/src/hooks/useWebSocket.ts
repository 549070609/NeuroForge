import { useCallback, useEffect, useRef, useState } from "react";
import type { WSEvent } from "../types";

const HEARTBEAT_INTERVAL_MS = 25_000;
const HEARTBEAT_TIMEOUT_MS = 10_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;
const MAX_RECONNECT_ATTEMPTS = 20;

interface UseWebSocketOptions {
  url: string;
  onMessage?: (event: WSEvent) => void;
  autoConnect?: boolean;
}

export function useWebSocket({ url, onMessage, autoConnect = true }: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const mountedRef = useRef(true);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval>>(undefined);
  const heartbeatTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);
  const reconnectAttempts = useRef(0);
  const intentionalClose = useRef(false);
  // Stable ref so scheduleReconnect always calls the latest connectInternal
  const connectInternalRef = useRef<() => void>(() => {});

  const stopHeartbeat = useCallback(() => {
    clearInterval(heartbeatTimer.current);
    clearTimeout(heartbeatTimeout.current);
    heartbeatTimer.current = undefined;
    heartbeatTimeout.current = undefined;
  }, []);

  const cleanup = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    stopHeartbeat();
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      if (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
    setConnected(false);
  }, [stopHeartbeat]);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current || intentionalClose.current) return;
    if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
      console.warn("[WS] max reconnect attempts reached, giving up");
      return;
    }

    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, reconnectAttempts.current),
      RECONNECT_MAX_MS,
    );
    reconnectAttempts.current += 1;
    console.log(`[WS] reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`);

    reconnectTimer.current = setTimeout(() => {
      if (mountedRef.current && !intentionalClose.current) {
        // Use ref to always call the latest version of connectInternal,
        // avoiding the stale closure that would otherwise hold url="".
        connectInternalRef.current();
      }
    }, delay);
  }, []);

  const startHeartbeat = useCallback((ws: WebSocket) => {
    stopHeartbeat();

    heartbeatTimer.current = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({ type: "ping" }));
        } catch {
          return;
        }

        heartbeatTimeout.current = setTimeout(() => {
          console.warn("[WS] heartbeat timeout, closing connection");
          ws.close();
        }, HEARTBEAT_TIMEOUT_MS);
      }
    }, HEARTBEAT_INTERVAL_MS);
  }, [stopHeartbeat]);

  const connectInternal = useCallback(() => {
    if (!url || !mountedRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) return;

    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      if (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (mountedRef.current) {
          setConnected(true);
          reconnectAttempts.current = 0;
          startHeartbeat(ws);
          console.log("[WS] connected:", url);
        }
      };

      ws.onmessage = (evt) => {
        let data: WSEvent;
        try {
          data = JSON.parse(evt.data);
        } catch {
          return; // ignore non-JSON frames
        }

        if (data.type === "pong") {
          clearTimeout(heartbeatTimeout.current);
          heartbeatTimeout.current = undefined;
          return;
        }

        onMessageRef.current?.(data);
      };

      ws.onclose = () => {
        if (mountedRef.current) {
          setConnected(false);
          wsRef.current = null;
          stopHeartbeat();
          console.log("[WS] closed:", url);
          scheduleReconnect();
        }
      };

      ws.onerror = (err) => {
        console.error("[WS] error:", err);
        ws.close();
      };
    } catch (err) {
      console.error("[WS] failed to create:", err);
      scheduleReconnect();
    }
  }, [url, startHeartbeat, stopHeartbeat, scheduleReconnect]);

  // Keep the ref up to date so scheduleReconnect always calls the latest version
  connectInternalRef.current = connectInternal;

  const connect = useCallback(() => {
    intentionalClose.current = false;
    reconnectAttempts.current = 0;
    connectInternal();
  }, [connectInternal]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
      return true;
    }
    console.warn("[WS] send failed: not connected");
    return false;
  }, []);

  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    cleanup();
  }, [cleanup]);

  useEffect(() => {
    mountedRef.current = true;
    intentionalClose.current = false;
    if (autoConnect && url) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      intentionalClose.current = true;
      cleanup();
    };
  }, [url, autoConnect, connect, cleanup]);

  return { connected, send, disconnect, connect };
}
