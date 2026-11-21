import type { TickerMeta } from "../lib/types";
import { formatPrice, formatPct } from "../lib/format";

interface Props {
  meta?: TickerMeta;
  ticker: string;
  price: number;
  change24h?: number;
}

export function PriceHeader({ meta, ticker, price, change24h = 0 }: Props) {
  const up = change24h >= 0;
  return (
    <div className="panel px-5 py-4 flex items-center justify-between">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-lg text-fg-primary">{ticker}</span>
        {meta && <span className="text-sm text-fg-secondary">{meta.name}</span>}
        {meta && (
          <span className="pill border-line text-fg-muted">{meta.asset_class.toUpperCase()}</span>
        )}
      </div>
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
  );
}
