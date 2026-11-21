import type { Indicators } from "../lib/types";
import { formatNum } from "../lib/format";

interface Props {
  indicators: Indicators;
}

export function IndicatorStrip({ indicators: ind }: Props) {
  const rsi = ind.rsi ?? null;
  const rsiTone =
    rsi == null
      ? "text-fg-primary"
      : rsi < 30
      ? "text-accent-long"
      : rsi > 70
      ? "text-accent-short"
      : "text-fg-primary";

  return (
    <div className="panel px-4 py-3 grid grid-cols-6 gap-x-6 gap-y-2">
      <Cell label="RSI 14" value={formatNum(ind.rsi, 1)} toneClass={rsiTone} />
      <Cell label="MACD" value={formatNum(ind.macd, 3)} />
      <Cell label="Signal" value={formatNum(ind.macd_signal, 3)} />
      <Cell label="ATR" value={formatNum(ind.atr, 3)} />
      <Cell label="SMA 20" value={formatNum(ind.sma20, 2)} />
      <Cell label="SMA 50" value={formatNum(ind.sma50, 2)} />
    </div>
  );
}

function Cell({ label, value, toneClass }: { label: string; value: string; toneClass?: string }) {
  return (
    <div className="flex flex-col">
      <span className="label">{label}</span>
      <span className={`font-mono num text-sm mt-0.5 ${toneClass ?? "text-fg-primary"}`}>{value}</span>
    </div>
  );
}
