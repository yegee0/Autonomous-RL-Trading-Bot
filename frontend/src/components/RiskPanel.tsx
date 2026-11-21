import type { PositionSizing, RiskMetrics } from "../lib/types";
import { formatPrice, formatPct, formatNum } from "../lib/format";

interface Props {
  risk: RiskMetrics;
  sizing: PositionSizing;
}

export function RiskPanel({ risk, sizing }: Props) {
  return (
    <div className="panel p-4 flex flex-col gap-4">
      <div>
        <div className="label mb-2">Trade Setup</div>
        <Row k="Size" v={`$${formatPrice(sizing.position_size_usd)}`} />
        <Row k="Stop" v={`$${formatPrice(sizing.stop_loss)}`} tone="short" />
        <Row k="Target" v={`$${formatPrice(sizing.take_profit)}`} tone="long" />
        <Row k="Kelly" v={formatPct(sizing.kelly_fraction / 100, 1)} />
      </div>

      <div className="hairline -mx-4" />

      <div>
        <div className="label mb-2">Risk Metrics</div>
        <Row k="Sharpe" v={formatNum(risk.sharpe_ratio)} />
        <Row k="Sortino" v={formatNum(risk.sortino_ratio)} />
        <Row k="Max DD" v={formatPct(risk.max_drawdown)} tone="short" />
        <Row k="Volatility" v={formatPct(risk.volatility)} />
        <Row k="VaR 95" v={formatPct(risk.var_95)} />
      </div>
    </div>
  );
}

function Row({ k, v, tone }: { k: string; v: string; tone?: "long" | "short" }) {
  const toneCls =
    tone === "long" ? "text-accent-long" : tone === "short" ? "text-accent-short" : "text-fg-primary";
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-fg-secondary">{k}</span>
      <span className={`font-mono num ${toneCls}`}>{v}</span>
    </div>
  );
}
