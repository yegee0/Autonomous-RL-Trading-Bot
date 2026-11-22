import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Activity } from "lucide-react";
import { api } from "../lib/api";
import { formatPct, formatNum } from "../lib/format";

interface Props {
  ticker: string;
}

export function DriftPanel({ ticker }: Props) {
  const [enabled, setEnabled] = useState(false);
  const q = useQuery({
    queryKey: ["drift", ticker],
    queryFn: () => api.drift(ticker, "1y", "1d"),
    enabled,
    retry: 0,
    staleTime: 10 * 60_000,
  });

  const d = q.data;
  const level = d?.level;
  const score = d?.drift_score ?? 0;

  const tone =
    level === "retrain"
      ? "text-accent-short"
      : level === "watch"
      ? "text-accent-neutral"
      : "text-accent-long";
  const label =
    level === "retrain"
      ? "Retrain recommended"
      : level === "watch"
      ? "Watch"
      : level === "ok"
      ? "Stable"
      : "—";

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">Concept drift</span>
        <button
          onClick={() => setEnabled(true)}
          disabled={q.isFetching}
          className="btn"
        >
          <Activity size={12} />
          {q.isFetching ? "Analysing…" : d ? "Rerun" : "Run"}
        </button>
      </div>

      {!enabled && (
        <p className="text-xs text-fg-muted">
          Compares recent 20% of bars with the preceding baseline: return
          distribution, policy action mix, and realised PnL.
        </p>
      )}
      {q.isError && <p className="text-xs text-accent-short">Drift analysis failed.</p>}
      {d && !d.ok && <p className="text-xs text-accent-short">{d.reason ?? "Not enough data."}</p>}

      {d?.ok && (
        <>
          <div className="flex items-baseline gap-3">
            <span className={`text-2xl font-semibold font-mono num ${tone}`}>
              {(score * 100).toFixed(0)}
            </span>
            <span className={`text-2xs uppercase tracking-wider ${tone}`}>{label}</span>
          </div>
          <div className="h-1 w-full bg-bg-panel2 rounded-full overflow-hidden">
            <div
              className={
                level === "retrain"
                  ? "h-full bg-accent-short"
                  : level === "watch"
                  ? "h-full bg-accent-neutral"
                  : "h-full bg-accent-long"
              }
              style={{ width: `${Math.min(100, score * 100)}%` }}
            />
          </div>

          <div className="grid grid-cols-3 gap-2 pt-1">
            <Mini k="Return" v={formatPct(d.return_drift ?? 0, 0)} />
            <Mini k="Policy" v={formatPct(d.policy_drift ?? 0, 0)} />
            <Mini k="PnL" v={formatPct(d.pnl_drift ?? 0, 0)} />
          </div>

          <div className="hairline -mx-4" />
          <div className="text-2xs grid grid-cols-3 gap-2">
            <div>
              <div className="label">Σ Baseline</div>
              <div className="font-mono num mt-1">σ {formatNum(d.baseline?.std, 3)}</div>
              <div className="font-mono num">
                buy {formatPct(d.baseline?.buy_pct ?? 0, 0)}
              </div>
              <div className="font-mono num">
                ret {formatPct(d.baseline?.total_return ?? 0, 1)}
              </div>
            </div>
            <div className="flex items-center justify-center text-fg-muted">→</div>
            <div>
              <div className="label">Σ Recent</div>
              <div className="font-mono num mt-1">σ {formatNum(d.recent?.std, 3)}</div>
              <div className="font-mono num">
                buy {formatPct(d.recent?.buy_pct ?? 0, 0)}
              </div>
              <div className="font-mono num">
                ret {formatPct(d.recent?.total_return ?? 0, 1)}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Mini({ k, v }: { k: string; v: string }) {
  return (
    <div className="bg-bg-panel2 rounded px-2 py-1.5">
      <div className="label">{k}</div>
      <div className="font-mono num text-sm text-fg-primary">{v}</div>
    </div>
  );
}
