import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldAlert, ShieldCheck, ShieldOff } from "lucide-react";
import { api } from "../lib/api";
import { formatPct } from "../lib/format";

export function GuardrailStatus() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["guardrails"],
    queryFn: api.guardrails,
    refetchInterval: 20_000,
  });

  const resetM = useMutation({
    mutationFn: api.guardrailsReset,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["guardrails"] }),
  });

  const s = q.data;
  if (!s) return null;

  const killActive = s.kill_switch_active;
  const Icon = killActive ? ShieldOff : s.daily_loss_tripped ? ShieldAlert : ShieldCheck;
  const tone = killActive
    ? "text-accent-short"
    : s.daily_loss_tripped
    ? "text-accent-neutral"
    : "text-accent-long";
  const label = killActive
    ? "KILLED"
    : s.daily_loss_tripped
    ? "DAILY LOSS TRIPPED"
    : "ARMED";

  const rateUtil = s.rate_hits_in_window / Math.max(1, s.rate_limit_max);

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label">Risk Guardrails</span>
        <div className={`flex items-center gap-1 ${tone}`}>
          <Icon size={12} />
          <span className="text-2xs uppercase tracking-wider font-semibold">{label}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
        <Row k="Max position" v={formatPct(s.limits.max_position_pct)} />
        <Row k="Max order" v={formatPct(s.limits.max_order_pct)} />
        <Row k="Daily loss cap" v={formatPct(s.limits.max_daily_loss_pct)} />
        <Row k="Rate limit" v={`${s.rate_limit_max}/${s.rate_limit_window_s}s`} />
        <Row k="RSI buy block" v={`≥ ${s.limits.rsi_buy_block.toFixed(0)}`} />
        <Row k="RSI sell block" v={`≤ ${s.limits.rsi_sell_block.toFixed(0)}`} />
      </div>

      <div>
        <div className="flex justify-between text-2xs text-fg-muted">
          <span>Rate usage</span>
          <span className="font-mono num">
            {s.rate_hits_in_window} / {s.rate_limit_max}
          </span>
        </div>
        <div className="h-1 w-full bg-bg-panel2 rounded-full overflow-hidden mt-1">
          <div
            className={rateUtil > 0.8 ? "bg-accent-short h-full" : "bg-accent-long h-full"}
            style={{ width: `${Math.min(100, rateUtil * 100)}%` }}
          />
        </div>
      </div>

      {killActive && (
        <button
          onClick={() => resetM.mutate()}
          disabled={resetM.isPending}
          className="h-8 w-full rounded border border-accent-short/40 bg-accent-short/10 text-accent-short text-xs font-semibold hover:bg-accent-short/20 disabled:opacity-40"
        >
          {resetM.isPending ? "Resetting…" : "Reset kill switch"}
        </button>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-fg-secondary">{k}</span>
      <span className="font-mono num text-fg-primary">{v}</span>
    </div>
  );
}
