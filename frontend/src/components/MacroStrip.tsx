import type { MacroSnapshot } from "../lib/types";
import { formatNum, formatPct } from "../lib/format";

interface Props {
  macro?: MacroSnapshot | null;
  loading?: boolean;
}

export function MacroStrip({ macro, loading }: Props) {
  if (loading) {
    return (
      <div className="panel px-4 py-3 flex gap-6 items-center text-fg-muted text-xs">
        Loading market context…
      </div>
    );
  }
  if (!macro) return null;

  const fg = macro.fear_greed ?? null;
  const fgLabel = macro.fear_greed_label ?? "—";
  const fgTone =
    fg == null
      ? "text-fg-muted"
      : fg < 25
      ? "text-accent-short"
      : fg < 45
      ? "text-accent-neutral"
      : fg < 55
      ? "text-fg-secondary"
      : fg < 75
      ? "text-accent-long"
      : "text-accent-long";

  return (
    <div className="panel px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-6">
        <MacroCell
          label="VIX"
          value={macro.vix?.value}
          delta={macro.vix?.delta}
          digits={2}
          invert
        />
        <MacroCell
          label="US10Y"
          value={macro.us10y?.value}
          delta={macro.us10y?.delta}
          digits={2}
        />
        <MacroCell
          label="DXY"
          value={macro.dxy?.value}
          delta={macro.dxy?.delta}
          digits={2}
        />
      </div>

      <div className="flex items-center gap-3">
        <div className="label">Fear & Greed</div>
        <FearGauge score={fg} />
        <div className={`text-2xs uppercase tracking-wider ${fgTone}`}>
          {fg != null ? `${fg.toFixed(0)} · ${fgLabel}` : "—"}
        </div>
      </div>
    </div>
  );
}

function MacroCell({
  label,
  value,
  delta,
  digits = 2,
  invert = false,
}: {
  label: string;
  value?: number | null;
  delta?: number | null;
  digits?: number;
  invert?: boolean;
}) {
  const up = (delta ?? 0) >= 0;
  const toneUp = invert ? "text-accent-short" : "text-accent-long";
  const toneDown = invert ? "text-accent-long" : "text-accent-short";
  const tone = delta == null ? "text-fg-muted" : up ? toneUp : toneDown;
  return (
    <div className="flex flex-col">
      <span className="label">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="font-mono num text-sm text-fg-primary">{formatNum(value ?? null, digits)}</span>
        <span className={`text-2xs font-mono num ${tone}`}>
          {delta == null ? "" : `${delta >= 0 ? "+" : ""}${formatPct(delta, 2)}`}
        </span>
      </div>
    </div>
  );
}

function FearGauge({ score }: { score: number | null }) {
  const s = score ?? 50;
  const pct = Math.max(0, Math.min(100, s));
  return (
    <div className="relative w-24 h-1.5 rounded-full bg-gradient-to-r from-accent-short via-accent-neutral to-accent-long">
      <div
        className="absolute top-1/2 -translate-y-1/2 w-0.5 h-3 bg-fg-primary rounded"
        style={{ left: `${pct}%` }}
      />
    </div>
  );
}
