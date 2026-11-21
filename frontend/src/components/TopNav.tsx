import { Activity } from "lucide-react";
import { TickerSearch } from "./TickerSearch";
import type { TickerMeta } from "../lib/types";

interface Props {
  tickers: TickerMeta[];
  ticker: string;
  onTicker: (t: string) => void;
  timeframe: string;
  onTimeframe: (t: string) => void;
  connected: boolean;
}

const TIMEFRAMES: { id: string; label: string; period: string; interval: string }[] = [
  { id: "1D", label: "1D", period: "5d", interval: "15m" },
  { id: "1W", label: "1W", period: "1mo", interval: "1h" },
  { id: "1M", label: "1M", period: "3mo", interval: "1d" },
  { id: "3M", label: "3M", period: "6mo", interval: "1d" },
  { id: "1Y", label: "1Y", period: "1y", interval: "1d" },
];

export { TIMEFRAMES };

export function TopNav({ tickers, ticker, onTicker, timeframe, onTimeframe, connected }: Props) {
  return (
    <header className="hairline px-4 sm:px-6 py-3 flex flex-col sm:flex-row sm:h-14 sm:items-center sm:justify-between gap-3 bg-bg-base">
      <div className="flex items-center gap-4 sm:gap-6 min-w-0">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-6 h-6 rounded bg-accent-long/15 flex items-center justify-center">
            <Activity size={14} className="text-accent-long" />
          </div>
          <span className="font-semibold tracking-tight">TradeMaster</span>
        </div>
        <TickerSearch tickers={tickers} value={ticker} onChange={onTicker} />
      </div>

      <div className="flex items-center gap-3 sm:gap-4 justify-between sm:justify-end">
        <div className="flex gap-0.5 p-0.5 bg-bg-panel border border-line rounded-md">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.id}
              onClick={() => onTimeframe(tf.id)}
              className={`px-2 sm:px-2.5 h-7 text-2xs uppercase tracking-wider rounded transition-colors ${
                timeframe === tf.id
                  ? "bg-bg-hover text-fg-primary"
                  : "text-fg-secondary hover:text-fg-primary"
              }`}
            >
              {tf.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5 text-2xs text-fg-muted shrink-0">
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              connected ? "bg-accent-long shadow-[0_0_6px_rgba(74,222,128,0.8)]" : "bg-fg-dim"
            }`}
          />
          {connected ? "Live" : "Idle"}
        </div>
      </div>
    </header>
  );
}
