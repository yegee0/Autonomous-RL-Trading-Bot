import { useMemo } from "react";
import { Flame } from "lucide-react";
import { useLiquidations } from "../hooks/useOrderBook";
import { formatCompact, formatPrice } from "../lib/format";

interface Props {
  ticker: string;
  enabled: boolean;
}

export function LiquidationFeed({ ticker, enabled }: Props) {
  const { events, connected } = useLiquidations(ticker, enabled, 25);

  const totals = useMemo(() => {
    let longUsd = 0,
      shortUsd = 0;
    for (const e of events) {
      if (e.side === "long") longUsd += e.usd;
      else shortUsd += e.usd;
    }
    return { longUsd, shortUsd, total: longUsd + shortUsd };
  }, [events]);

  if (!enabled) {
    return (
      <div className="panel p-4 text-xs text-fg-muted">
        Liquidations are only available for crypto pairs.
      </div>
    );
  }

  const longPct = totals.total > 0 ? totals.longUsd / totals.total : 0;

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <Flame size={12} /> Liquidations
        </span>
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            connected ? "bg-accent-long" : "bg-fg-dim"
          }`}
        />
      </div>

      <div>
        <div className="flex justify-between text-2xs text-fg-muted">
          <span className="text-accent-long">Longs ${formatCompact(totals.longUsd)}</span>
          <span className="text-accent-short">Shorts ${formatCompact(totals.shortUsd)}</span>
        </div>
        <div className="h-1 flex rounded-full overflow-hidden bg-bg-panel2 mt-1">
          <div className="h-full bg-accent-long" style={{ width: `${longPct * 100}%` }} />
          <div className="h-full bg-accent-short" style={{ width: `${(1 - longPct) * 100}%` }} />
        </div>
      </div>

      <ul className="space-y-1 max-h-48 overflow-y-auto">
        {events.length === 0 ? (
          <li className="text-xs text-fg-muted text-center py-4">Waiting for liquidations…</li>
        ) : (
          events.map((e, i) => (
            <li
              key={i}
              className="flex items-center justify-between text-2xs font-mono num leading-5"
            >
              <span
                className={e.side === "long" ? "text-accent-short" : "text-accent-long"}
              >
                {e.side === "long" ? "LONG REKT" : "SHORT REKT"}
              </span>
              <span className="text-fg-secondary">${formatPrice(e.price, 2)}</span>
              <span className="text-fg-primary">${formatCompact(e.usd)}</span>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
