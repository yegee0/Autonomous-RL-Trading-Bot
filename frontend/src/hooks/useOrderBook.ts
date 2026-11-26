import { useEffect, useRef, useState } from "react";

export interface DepthSnapshot {
  bids: [number, number][];
  asks: [number, number][];
}

export interface Liquidation {
  symbol: string;
  side: "long" | "short";
  price: number;
  qty: number;
  usd: number;
  time: number | null;
}

function wsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

export function useOrderBook(ticker: string, enabled: boolean) {
  const [snapshot, setSnapshot] = useState<DepthSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled || !ticker) {
      setConnected(false);
      setSnapshot(null);
      return;
    }

    let cancelled = false;
    let retry: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(wsUrl(`/ws/depth/${ticker}`));
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
          setSnapshot(data as DepthSnapshot);
        } catch {
          /* ignore */
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (retry) clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [ticker, enabled]);

  return { snapshot, connected };
}

export function useLiquidations(ticker: string, enabled: boolean, max = 30) {
  const [events, setEvents] = useState<Liquidation[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled || !ticker) {
      setConnected(false);
      setEvents([]);
      return;
    }
    let cancelled = false;
    let retry: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(wsUrl(`/ws/liquidations/${ticker}`));
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
          setEvents((prev) => [data as Liquidation, ...prev].slice(0, max));
        } catch {
          /* ignore */
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (retry) clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [ticker, enabled, max]);

  return { events, connected };
}
