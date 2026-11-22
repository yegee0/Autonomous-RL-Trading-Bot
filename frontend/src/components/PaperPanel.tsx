import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";
import { formatPrice, formatPct } from "../lib/format";

interface Props {
  ticker: string;
  livePrice: number;
}

export function PaperPanel({ ticker, livePrice }: Props) {
  const qc = useQueryClient();
  const [qty, setQty] = useState(1);

  const portfolioQ = useQuery({
    queryKey: ["paper", "portfolio"],
    queryFn: api.paperPortfolio,
    refetchInterval: 15_000,
  });

  const tradesQ = useQuery({
    queryKey: ["paper", "trades", ticker],
    queryFn: () => api.paperTrades(10, ticker),
    refetchInterval: 15_000,
  });

  const tradeM = useMutation({
    mutationFn: api.paperTrade,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["paper"] });
    },
  });

  const resetM = useMutation({
    mutationFn: api.paperReset,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["paper"] }),
  });

  const portfolio = portfolioQ.data;
  const position = portfolio?.positions.find((p) => p.ticker === ticker);

  function submit(side: "buy" | "sell") {
    if (!livePrice || qty <= 0) return;
    tradeM.mutate({ ticker, side, qty, price: livePrice });
  }

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">Paper Trading</span>
        <button
          onClick={() => resetM.mutate()}
          className="btn-ghost"
          disabled={resetM.isPending}
        >
          Reset
        </button>
      </div>

      {portfolio && (
        <div className="grid grid-cols-2 gap-2 pt-1">
          <Stat k="Cash" v={`$${formatPrice(portfolio.cash, 0)}`} />
          <Stat k="Equity" v={`$${formatPrice(portfolio.total_equity, 0)}`} />
        </div>
      )}

      {position && (
        <div className="bg-bg-panel2 rounded p-2 text-xs">
          <div className="flex justify-between">
            <span className="text-fg-secondary">Position</span>
            <span className="font-mono num">{position.qty.toFixed(4)} @ ${formatPrice(position.avg_cost)}</span>
          </div>
          {position.unrealized_pnl != null && (
            <div className="flex justify-between mt-1">
              <span className="text-fg-secondary">Unrealized</span>
              <span
                className={`font-mono num ${
                  position.unrealized_pnl >= 0 ? "text-accent-long" : "text-accent-short"
                }`}
              >
                ${formatPrice(position.unrealized_pnl)} ({formatPct(position.unrealized_pnl / (position.qty * position.avg_cost || 1))})
              </span>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2">
        <input
          type="number"
          value={qty}
          min={0}
          step={0.01}
          onChange={(e) => setQty(Number(e.target.value))}
          className="flex-1 h-8 px-2 bg-bg-panel border border-line rounded text-sm font-mono num text-fg-primary outline-none focus:border-line-strong"
          placeholder="qty"
        />
        <span className="text-xs text-fg-muted">× ${formatPrice(livePrice)}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => submit("buy")}
          disabled={!livePrice || tradeM.isPending}
          className="h-8 rounded border border-accent-long/40 bg-accent-long/10 text-accent-long text-xs font-semibold hover:bg-accent-long/20 disabled:opacity-40"
        >
          Buy
        </button>
        <button
          onClick={() => submit("sell")}
          disabled={!livePrice || tradeM.isPending}
          className="h-8 rounded border border-accent-short/40 bg-accent-short/10 text-accent-short text-xs font-semibold hover:bg-accent-short/20 disabled:opacity-40"
        >
          Sell
        </button>
      </div>

      {tradeM.isError && (
        <p className="text-2xs text-accent-short">
          {formatTradeError(tradeM.error)}
        </p>
      )}

      {!!tradesQ.data?.length && (
        <div className="pt-1">
          <div className="label mb-1">Recent trades</div>
          <ul className="space-y-1 max-h-32 overflow-y-auto">
            {tradesQ.data.slice(0, 5).map((t) => (
              <li key={t.id} className="flex justify-between text-2xs font-mono num">
                <span
                  className={t.side === "buy" ? "text-accent-long" : "text-accent-short"}
                >
                  {t.side.toUpperCase()}
                </span>
                <span>{t.qty.toFixed(4)} @ ${formatPrice(t.price)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="label">{k}</div>
      <div className="font-mono num text-sm text-fg-primary mt-0.5">{v}</div>
    </div>
  );
}

function formatTradeError(err: unknown): string {
  const data = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (!data) return "Trade failed.";
  if (typeof data === "string") return data;
  if (typeof data === "object") {
    const d = data as { code?: string; message?: string };
    if (d.message) return d.code ? `${d.code}: ${d.message}` : d.message;
  }
  return "Trade rejected by guardrails.";
}
