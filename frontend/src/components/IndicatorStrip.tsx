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

  const stochK = ind.stoch_k ?? null;
  const stochTone =
    stochK == null
      ? "text-fg-primary"
      : stochK < 20
      ? "text-accent-long"
      : stochK > 80
      ? "text-accent-short"
      : "text-fg-primary";

  const macdDiff =
    ind.macd != null && ind.macd_signal != null ? ind.macd - ind.macd_signal : null;
  const macdTone =
    macdDiff == null
      ? "text-fg-primary"
      : macdDiff > 0
      ? "text-accent-long"
      : "text-accent-short";

  const volRatio = ind.volume_ratio ?? null;
  const volTone =
    volRatio == null
      ? "text-fg-primary"
      : volRatio > 1.5
      ? "text-accent-long"
      : volRatio < 0.5
      ? "text-accent-short"
      : "text-fg-primary";

  return (
    <div className="panel px-4 py-3 grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-x-6 gap-y-2">
      <Cell label="RSI 14" value={formatNum(ind.rsi, 1)} toneClass={rsiTone} />
      <Cell label="MACD" value={formatNum(ind.macd, 3)} toneClass={macdTone} />
      <Cell label="Signal" value={formatNum(ind.macd_signal, 3)} />
      <Cell label="Stoch %K" value={formatNum(ind.stoch_k, 1)} toneClass={stochTone} />
      <Cell label="Stoch %D" value={formatNum(ind.stoch_d, 1)} />
      <Cell label="ATR" value={formatNum(ind.atr, 3)} />
      <Cell label="SMA 20" value={formatNum(ind.sma20, 2)} />
      <Cell label="SMA 50" value={formatNum(ind.sma50, 2)} />
      <Cell label="Vol x" value={formatNum(ind.volume_ratio, 2)} toneClass={volTone} />
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
