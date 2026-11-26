import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown } from "lucide-react";
import { api } from "../lib/api";
import { formatCompact, formatPct } from "../lib/format";

interface Props {
  ticker: string;
  enabled: boolean;
}

export function OnChainCard({ ticker, enabled }: Props) {
  const q = useQuery({
    queryKey: ["onchain", ticker],
    queryFn: () => api.onchain(ticker),
    enabled,
    refetchInterval: 60_000,
    retry: 0,
  });

  if (!enabled) {
    return (
      <div className="panel p-4 text-xs text-fg-muted">
        Funding / OI is only available for perpetual-futures pairs.
      </div>
    );
  }

  const d = q.data;
  const fr = d?.funding_rate ?? null;
  const fr_ann = d?.funding_annualized ?? null;
  const oi_chg = d?.oi_change_24h ?? null;

  const frTone =
    fr == null ? "text-fg-muted" : fr > 1e-4 ? "text-accent-short" : fr < -1e-4 ? "text-accent-long" : "text-fg-secondary";
  const oiTone = oi_chg == null ? "text-fg-muted" : oi_chg >= 0 ? "text-accent-long" : "text-accent-short";

  const crowded = d?.crowded_side ?? null;
  const crowdedLabel =
    crowded === "long" ? "Longs crowded" : crowded === "short" ? "Shorts crowded" : "Balanced";
  const crowdedTone =
    crowded === "long" ? "text-accent-short" : crowded === "short" ? "text-accent-long" : "text-fg-secondary";

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">Perpetual futures</span>
        <span className={`text-2xs uppercase tracking-wider ${crowdedTone}`}>{crowdedLabel}</span>
      </div>

      {!d && q.isLoading && <div className="text-xs text-fg-muted">Loading…</div>}
      {q.isError && <div className="text-xs text-accent-short">Unavailable.</div>}

      {d && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Stat
              label="Funding"
              value={fr == null ? "—" : `${(fr * 100).toFixed(4)}%`}
              tone={frTone}
              sub={fr_ann == null ? "" : `ann ${formatPct(fr_ann, 1)}`}
            />
            <Stat
              label="OI 24h Δ"
              value={oi_chg == null ? "—" : formatPct(oi_chg, 2)}
              tone={oiTone}
              sub={oi_chg == null ? "" : oi_chg >= 0 ? "build-up" : "unwind"}
              icon={oi_chg == null ? null : oi_chg >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
            />
            <Stat
              label="Open Interest"
              value={d.open_interest_usd ? `$${formatCompact(d.open_interest_usd)}` : d.open_interest?.toFixed(0) ?? "—"}
            />
            <Stat
              label="Mark"
              value={d.mark_price ? `$${d.mark_price.toLocaleString("en-US", { maximumFractionDigits: 2 })}` : "—"}
            />
          </div>
          {d.next_funding_time && (
            <div className="text-2xs text-fg-muted">
              next funding · {new Date(d.next_funding_time * 1000).toLocaleTimeString()}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  sub,
  icon,
}: {
  label: string;
  value: string;
  tone?: string;
  sub?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className={`font-mono num text-sm mt-0.5 flex items-center gap-1 ${tone ?? "text-fg-primary"}`}>
        {icon}
        {value}
      </div>
      {sub && <div className="text-2xs text-fg-muted">{sub}</div>}
    </div>
  );
}
