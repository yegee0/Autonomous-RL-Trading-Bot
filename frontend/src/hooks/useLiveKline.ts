import { useEffect, useRef, useState } from "react";
import type { LiveKline } from "../lib/types";
import { liveWsUrl } from "../lib/api";

export function useLiveKline(ticker: string, enabled: boolean): { kline: LiveKline | null; connected: boolean } {
  const [kline, setKline] = useState<LiveKline | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled || !ticker) {
      setConnected(false);
      return;
    }

    let cancelled = false;
    let retry: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(liveWsUrl(ticker));
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) retry = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          if (data.error) return;
          setKline(data as LiveKline);
        } catch (e) {
          console.warn("ws parse error", e);
        }
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (retry) clearTimeout(retry);
      wsRef.current?.close();
      setConnected(false);
    };
  }, [ticker, enabled]);

  return { kline, connected };
}
