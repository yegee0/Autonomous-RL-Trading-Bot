import { ArrowDown, ArrowUp, Minus, Cpu, Activity } from "lucide-react";
import type { Indicators, SignalResponse } from "../lib/types";
import { formatPrice, formatPct } from "../lib/format";

interface Props {
  signal: SignalResponse;
  price: number;
  indicators?: Indicators;
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

export function SignalCard({ signal, price, indicators }: Props) {
  const isLong = signal.direction === "long";
  const isShort = signal.direction === "short";
  const Icon = isLong ? ArrowUp : isShort ? ArrowDown : Minus;
  const accent = isLong ? "text-accent-long" : isShort ? "text-accent-short" : "text-accent-neutral";
  const bar = isLong ? "bg-accent-long" : isShort ? "bg-accent-short" : "bg-accent-neutral";

  const reasons = buildReasons(indicators, signal.sentiment);

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

      {reasons.length > 0 && (
        <div className="pt-2 border-t border-line">
          <div className="label mb-1.5">Why</div>
          <ul className="space-y-1">
            {reasons.map((r, i) => (
              <li key={i} className="text-xs flex items-start gap-1.5">
                <span
                  className={`mt-1 w-1 h-1 rounded-full shrink-0 ${
                    r.tone === "long"
                      ? "bg-accent-long"
                      : r.tone === "short"
                      ? "bg-accent-short"
                      : "bg-fg-dim"
                  }`}
                />
                <span className="text-fg-secondary">{r.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function buildReasons(
  ind: Indicators | undefined,
  sentiment: number
): { text: string; tone: "long" | "short" | "neutral" }[] {
  if (!ind) return [];
  const out: { text: string; tone: "long" | "short" | "neutral" }[] = [];

  if (ind.rsi != null) {
    if (ind.rsi < 30)
      out.push({ text: `RSI ${ind.rsi.toFixed(1)} — oversold`, tone: "long" });
    else if (ind.rsi > 70)
      out.push({ text: `RSI ${ind.rsi.toFixed(1)} — overbought`, tone: "short" });
  }

  if (ind.macd != null && ind.macd_signal != null) {
    const diff = ind.macd - ind.macd_signal;
    if (Math.abs(diff) > 1e-5) {
      out.push({
        text: diff > 0 ? "MACD above signal — bullish momentum" : "MACD below signal — bearish momentum",
        tone: diff > 0 ? "long" : "short",
      });
    }
  }

  if (ind.stoch_k != null) {
    if (ind.stoch_k < 20) out.push({ text: `Stoch %K ${ind.stoch_k.toFixed(0)} — oversold`, tone: "long" });
    else if (ind.stoch_k > 80) out.push({ text: `Stoch %K ${ind.stoch_k.toFixed(0)} — overbought`, tone: "short" });
  }

  if (ind.volume_ratio != null && ind.volume_ratio > 1.8) {
    out.push({ text: `Volume ${ind.volume_ratio.toFixed(1)}x average — high conviction`, tone: "neutral" });
  }

  if (Math.abs(sentiment) > 0.2) {
    out.push({
      text:
        sentiment > 0
          ? `News / social sentiment bullish (${sentiment.toFixed(2)})`
          : `News / social sentiment bearish (${sentiment.toFixed(2)})`,
      tone: sentiment > 0 ? "long" : "short",
    });
  }

  return out.slice(0, 4);
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
