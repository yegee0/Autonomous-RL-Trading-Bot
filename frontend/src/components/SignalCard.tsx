import { ArrowDown, ArrowUp, Minus, Cpu, Activity } from "lucide-react";
import type { SignalResponse } from "../lib/types";
import { formatPrice, formatPct } from "../lib/format";

interface Props {
  signal: SignalResponse;
  price: number;
}

const LABEL_MAP: Record<string, string> = {
  HOLD: "Hold",
  BUY_25: "Buy 25%",
  BUY_50: "Buy 50%",
  BUY_100: "Buy Full",
  SELL_25: "Sell 25%",
  SELL_50: "Sell 50%",
  SELL_100: "Sell Full",
};

export function SignalCard({ signal, price }: Props) {
  const isLong = signal.direction === "long";
  const isShort = signal.direction === "short";
  const Icon = isLong ? ArrowUp : isShort ? ArrowDown : Minus;
  const accent = isLong ? "text-accent-long" : isShort ? "text-accent-short" : "text-accent-neutral";
  const bar = isLong ? "bg-accent-long" : isShort ? "bg-accent-short" : "bg-accent-neutral";

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">Signal</span>
        <div className="flex items-center gap-1 text-fg-muted">
          {signal.source === "ppo" ? <Cpu size={12} /> : <Activity size={12} />}
          <span className="text-2xs uppercase tracking-wider">{signal.source}</span>
        </div>
      </div>

      <div className="flex items-baseline gap-3">
        <Icon size={28} strokeWidth={1.5} className={accent} />
        <span className={`text-2xl font-semibold ${accent}`}>
          {LABEL_MAP[signal.action_label] ?? signal.action_label}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-2">
        <Metric label="Price" value={formatPrice(price)} mono />
        <Metric label="Confidence" value={formatPct(signal.confidence, 1)} mono />
        <Metric label="Sentiment" value={signal.sentiment.toFixed(2)} mono />
        <Metric label="Direction" value={signal.direction.toUpperCase()} />
      </div>

      <div className="mt-1">
        <div className="h-1 w-full bg-bg-panel2 rounded-full overflow-hidden">
          <div
            className={`h-full ${bar}`}
            style={{ width: `${Math.max(4, Math.min(100, signal.confidence * 100))}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className={`${mono ? "font-mono num" : "font-medium"} text-sm text-fg-primary mt-0.5`}>
        {value}
      </div>
    </div>
  );
}
