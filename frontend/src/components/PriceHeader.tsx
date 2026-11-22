import type { Fundamentals, TickerMeta } from "../lib/types";
import { formatPrice, formatPct } from "../lib/format";

interface Props {
  meta?: TickerMeta;
  ticker: string;
  price: number;
  change24h?: number;
  fundamentals?: Fundamentals | null;
}

export function PriceHeader({ meta, ticker, price, change24h = 0, fundamentals }: Props) {
  const up = change24h >= 0;

  const low = fundamentals?.fifty_two_week_low ?? null;
  const high = fundamentals?.fifty_two_week_high ?? null;
  const rangePct =
    low != null && high != null && high > low
      ? Math.max(0, Math.min(100, ((price - low) / (high - low)) * 100))
      : null;

  return (
    <div className="panel px-5 py-4 flex items-center justify-between flex-wrap gap-4">
      <div className="flex items-baseline gap-3 min-w-0">
        <span className="font-mono text-lg text-fg-primary">{ticker}</span>
        {meta && <span className="text-sm text-fg-secondary truncate">{meta.name}</span>}
        {meta && (
          <span className="pill border-line text-fg-muted">{meta.asset_class.toUpperCase()}</span>
        )}
      </div>

      <div className="flex items-center gap-6 flex-wrap">
        {rangePct != null && (
          <div className="flex flex-col gap-1 w-40">
            <div className="flex justify-between text-2xs text-fg-muted font-mono num">
              <span>${formatPrice(low!, 2)}</span>
              <span className="label">52W Range</span>
              <span>${formatPrice(high!, 2)}</span>
            </div>
            <div className="relative h-1 rounded-full bg-bg-panel2 overflow-hidden">
              <div
                className="absolute top-0 h-1 w-0.5 bg-accent-info"
                style={{ left: `calc(${rangePct}% - 1px)` }}
              />
            </div>
          </div>
        )}
        <div className="flex items-baseline gap-4">
          <span className="font-mono num text-2xl font-semibold">${formatPrice(price)}</span>
          <span
            className={`font-mono num text-sm ${up ? "text-accent-long" : "text-accent-short"}`}
          >
            {up ? "+" : ""}
            {formatPct(change24h, 2)}
          </span>
        </div>
      </div>
    </div>
  );
}
