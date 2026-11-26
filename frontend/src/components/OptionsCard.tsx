import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingDown, Zap } from "lucide-react";
import { api } from "../lib/api";
import { formatPct } from "../lib/format";

interface Props {
  ticker: string;
  enabled: boolean;
}

export function OptionsCard({ ticker, enabled }: Props) {
  const [expiry, setExpiry] = useState<string | undefined>(undefined);

  const q = useQuery({
    queryKey: ["options", ticker, expiry],
    queryFn: () => api.options(ticker, expiry),
    enabled,
    retry: 0,
    staleTime: 2 * 60_000,
  });

  const skewPoints = useMemo(() => {
    const d = q.data;
    if (!d) return [];
    const puts = d.puts
      .filter((r) => r.implied_vol > 0 && r.open_interest > 0 && r.strike <= d.spot)
      .map((r) => ({ strike: r.strike, iv: r.implied_vol, kind: "put" as const }));
    const calls = d.calls
      .filter((r) => r.implied_vol > 0 && r.open_interest > 0 && r.strike >= d.spot)
      .map((r) => ({ strike: r.strike, iv: r.implied_vol, kind: "call" as const }));
    return [...puts, ...calls].sort((a, b) => a.strike - b.strike);
  }, [q.data]);

  if (!enabled) {
    return (
      <div className="panel p-4 text-xs text-fg-muted">
        Options are only available for US-listed stocks.
      </div>
    );
  }

  if (q.isLoading) return <div className="panel p-4 text-xs text-fg-muted">Loading option chain…</div>;
  if (q.isError || !q.data) {
    return <div className="panel p-4 text-xs text-accent-short">No option chain for {ticker}.</div>;
  }

  const d = q.data;
  const maxIv = Math.max(...skewPoints.map((p) => p.iv), 0.01);
  const pcTone = d.put_call_oi == null ? "text-fg-secondary" : d.put_call_oi > 1.2 ? "text-accent-short" : "text-accent-long";
  const skewTone = d.skew_25d == null ? "text-fg-secondary" : d.skew_25d > 0.03 ? "text-accent-short" : "text-accent-long";

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <Zap size={12} /> Options · {d.ticker}
        </span>
        <select
          className="text-2xs bg-bg-panel border border-line rounded px-1.5 py-0.5 text-fg-secondary"
          value={expiry ?? d.expiry}
          onChange={(e) => setExpiry(e.target.value)}
        >
          {d.expiries.map((e) => (
            <option key={e} value={e}>{e}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Spot" value={`$${d.spot.toFixed(2)}`} />
        <Stat label="ATM IV" value={d.atm_iv ? formatPct(d.atm_iv, 1) : "—"} />
        <Stat
          label="25Δ skew"
          tone={skewTone}
          value={d.skew_25d == null ? "—" : `${(d.skew_25d * 100).toFixed(2)}pp`}
          sub={d.skew_25d != null ? (d.skew_25d > 0 ? "puts bid" : "calls bid") : ""}
          icon={d.skew_25d != null && d.skew_25d > 0 ? <TrendingDown size={10} /> : null}
        />
        <Stat
          label="Put/Call OI"
          tone={pcTone}
          value={d.put_call_oi == null ? "—" : d.put_call_oi.toFixed(2)}
          sub={d.put_call_oi != null ? (d.put_call_oi > 1 ? "bearish" : "bullish") : ""}
        />
      </div>

      {skewPoints.length >= 4 && (
        <div>
          <div className="label mb-1">IV skew (near-money, OI-weighted)</div>
          <div className="relative h-24 border border-line rounded px-1">
            <div className="absolute inset-0 flex items-end gap-0.5 px-1 pb-1">
              {skewPoints.map((p, i) => {
                const h = Math.max(4, (p.iv / maxIv) * 90);
                const color = p.kind === "put" ? "bg-accent-short/70" : "bg-accent-long/70";
                return (
                  <div
                    key={i}
                    className={`flex-1 ${color} rounded-t`}
                    style={{ height: `${h}%` }}
                    title={`${p.strike} · ${(p.iv * 100).toFixed(1)}%`}
                  />
                );
              })}
            </div>
          </div>
          <div className="flex justify-between text-2xs text-fg-muted mt-0.5 font-mono num">
            <span>{skewPoints[0].strike.toFixed(0)}</span>
            <span>{skewPoints[skewPoints.length - 1].strike.toFixed(0)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label, value, tone, sub, icon,
}: { label: string; value: string; tone?: string; sub?: string; icon?: React.ReactNode }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className={`font-mono num text-sm mt-0.5 flex items-center gap-1 ${tone ?? "text-fg-primary"}`}>
        {icon}{value}
      </div>
      {sub && <div className="text-2xs text-fg-muted">{sub}</div>}
    </div>
  );
}
