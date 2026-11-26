import { useMemo } from "react";
import { useOrderBook } from "../hooks/useOrderBook";
import { formatPrice } from "../lib/format";

interface Props {
  ticker: string;
  enabled: boolean;
}

export function OrderBook({ ticker, enabled }: Props) {
  const { snapshot, connected } = useOrderBook(ticker, enabled);

  const { bids, asks, maxQty, bidSum, askSum, spread, mid } = useMemo(() => {
    if (!snapshot) {
      return { bids: [], asks: [], maxQty: 1, bidSum: 0, askSum: 0, spread: 0, mid: 0 };
    }
    const b = snapshot.bids.slice(0, 15);
    const a = snapshot.asks.slice(0, 15);
    const bs = b.reduce((s, [, q]) => s + q, 0);
    const as_ = a.reduce((s, [, q]) => s + q, 0);
    const mx = Math.max(...b.map(([, q]) => q), ...a.map(([, q]) => q), 1);
    const bestBid = b[0]?.[0] ?? 0;
    const bestAsk = a[0]?.[0] ?? 0;
    return {
      bids: b,
      asks: a,
      maxQty: mx,
      bidSum: bs,
      askSum: as_,
      spread: bestAsk > 0 && bestBid > 0 ? ((bestAsk - bestBid) / bestBid) * 100 : 0,
      mid: (bestAsk + bestBid) / 2,
    };
  }, [snapshot]);

  if (!enabled) {
    return (
      <div className="panel p-4 text-xs text-fg-muted">
        Order book is only available for crypto pairs.
      </div>
    );
  }

  const imbalance = bidSum + askSum > 0 ? (bidSum - askSum) / (bidSum + askSum) : 0;
  const imbTone = imbalance > 0.1 ? "text-accent-long" : imbalance < -0.1 ? "text-accent-short" : "text-fg-secondary";

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">Order book · L2</span>
        <div className="flex items-center gap-2">
          <span className={`text-2xs font-mono num ${imbTone}`}>
            imb {imbalance >= 0 ? "+" : ""}
            {(imbalance * 100).toFixed(0)}%
          </span>
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              connected ? "bg-accent-long" : "bg-fg-dim"
            }`}
          />
        </div>
      </div>

      {!snapshot && (
        <div className="text-xs text-fg-muted text-center py-6">Waiting for depth…</div>
      )}

      {snapshot && (
        <>
          {/* Asks: show highest at top, closest to mid at bottom */}
          <ul className="space-y-0.5 text-xs">
            {asks
              .slice()
              .reverse()
              .map(([price, qty], i) => {
                const pct = Math.min(100, (qty / maxQty) * 100);
                return (
                  <li key={`a${i}`} className="relative flex justify-between font-mono num leading-5">
                    <div
                      className="absolute right-0 top-0 h-full bg-accent-short/15"
                      style={{ width: `${pct}%` }}
                    />
                    <span className="relative text-accent-short">${formatPrice(price, 2)}</span>
                    <span className="relative text-fg-secondary">{qty.toFixed(4)}</span>
                  </li>
                );
              })}
          </ul>

          <div className="flex items-center justify-between text-2xs border-y border-line py-1">
            <span className="font-mono num text-fg-primary">${formatPrice(mid, 2)}</span>
            <span className="text-fg-muted">spread {spread.toFixed(3)}%</span>
          </div>

          <ul className="space-y-0.5 text-xs">
            {bids.map(([price, qty], i) => {
              const pct = Math.min(100, (qty / maxQty) * 100);
              return (
                <li key={`b${i}`} className="relative flex justify-between font-mono num leading-5">
                  <div
                    className="absolute right-0 top-0 h-full bg-accent-long/15"
                    style={{ width: `${pct}%` }}
                  />
                  <span className="relative text-accent-long">${formatPrice(price, 2)}</span>
                  <span className="relative text-fg-secondary">{qty.toFixed(4)}</span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
