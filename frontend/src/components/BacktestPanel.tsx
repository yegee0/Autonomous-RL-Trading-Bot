import { useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useState } from "react";
import { api } from "../lib/api";
import { formatPct, formatPrice, formatNum } from "../lib/format";

interface Props {
  ticker: string;
}

export function BacktestPanel({ ticker }: Props) {
  const [enabled, setEnabled] = useState(false);

  const q = useQuery({
    queryKey: ["backtest", ticker],
    queryFn: () => api.backtest(ticker, "6mo", "1d", 400),
    enabled,
    staleTime: 10 * 60_000,
    retry: 0,
  });

  const report = q.data;

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">Backtest · 6M daily</span>
        <button
          onClick={() => setEnabled(true)}
          disabled={q.isFetching}
          className="btn"
        >
          <Play size={12} />
          {q.isFetching ? "Running…" : report ? "Rerun" : "Run"}
        </button>
      </div>

      {!enabled && (
        <p className="text-xs text-fg-muted">Click Run to replay the policy on 6 months of daily bars.</p>
      )}

      {q.isError && <p className="text-xs text-accent-short">Backtest failed.</p>}

      {report && (
        <>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 pt-1">
            <Row k="Return" v={formatPct(report.total_return)} tone={report.total_return >= 0 ? "long" : "short"} />
            <Row k="Buy & Hold" v={formatPct(report.buy_hold_return)} />
            <Row k="Outperf." v={formatPct(report.outperformance)} tone={report.outperformance >= 0 ? "long" : "short"} />
            <Row k="Sharpe" v={formatNum(report.sharpe)} />
            <Row k="Max DD" v={formatPct(report.max_drawdown)} tone="short" />
            <Row k="Trades" v={report.total_trades.toString()} />
          </div>

          <div className="pt-2">
            <div className="label mb-1">Final equity</div>
            <div className="font-mono num text-sm text-fg-primary">${formatPrice(report.final_equity)}</div>
          </div>

          <div className="h-px bg-line my-1" />
          <Sparkline data={report.equity_curve} positive={report.total_return >= 0} />
        </>
      )}
    </div>
  );
}

function Row({ k, v, tone }: { k: string; v: string; tone?: "long" | "short" }) {
  const toneCls =
    tone === "long" ? "text-accent-long" : tone === "short" ? "text-accent-short" : "text-fg-primary";
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-fg-secondary">{k}</span>
      <span className={`font-mono num ${toneCls}`}>{v}</span>
    </div>
  );
}

function Sparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data.length) return null;
  const w = 288;
  const h = 48;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const step = w / Math.max(1, data.length - 1);
  const path = data
    .map((v, i) => `${i === 0 ? "M" : "L"}${i * step},${h - ((v - min) / range) * h}`)
    .join(" ");
  const color = positive ? "#4ADE80" : "#F43F5E";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-12">
      <path d={path} stroke={color} strokeWidth="1.5" fill="none" />
    </svg>
  );
}
