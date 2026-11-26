import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Shield } from "lucide-react";
import { api } from "../lib/api";
import { formatCompact, formatPct } from "../lib/format";

export function PortfolioRiskCard() {
  const q = useQuery({
    queryKey: ["portfolio-risk"],
    queryFn: api.portfolioRisk,
    refetchInterval: 60_000,
    retry: 0,
  });

  const d = q.data;

  if (!d && q.isLoading) {
    return <div className="panel p-4 text-xs text-fg-muted">Loading portfolio risk…</div>;
  }
  if (!d || q.isError) {
    return <div className="panel p-4 text-xs text-accent-short">Portfolio risk unavailable.</div>;
  }

  const expTone =
    d.gross_exposure_pct > 0.6 ? "text-accent-short"
    : d.gross_exposure_pct > 0.4 ? "text-accent-neutral"
    : "text-accent-long";

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <Shield size={12} /> Portfolio risk
        </span>
        <span className="text-2xs text-fg-muted">
          equity ${formatCompact(d.equity)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Gross exposure" value={formatPct(d.gross_exposure_pct, 1)} tone={expTone} />
        <Stat label="Biggest position" value={formatPct(d.concentration_pct, 1)} />
        <Stat
          label="VaR 95% (param)"
          value={d.var_95_parametric ? `-$${formatCompact(d.var_95_parametric)}` : "—"}
          sub="1-day"
        />
        <Stat
          label="VaR 95% (hist)"
          value={d.var_95_historical ? `-$${formatCompact(d.var_95_historical)}` : "—"}
          sub="1-day"
        />
        <Stat
          label="Portfolio vol"
          value={d.portfolio_vol_annualized ? formatPct(d.portfolio_vol_annualized, 1) : "—"}
          sub="annualized"
        />
        <Stat label="Positions" value={String(d.tickers.length)} />
      </div>

      {d.warnings.length > 0 && (
        <ul className="space-y-1">
          {d.warnings.map((w, i) => (
            <li key={i} className="flex items-center gap-1.5 text-2xs text-accent-neutral">
              <AlertTriangle size={10} /> {w}
            </li>
          ))}
        </ul>
      )}

      {d.tickers.length >= 2 && (
        <div>
          <div className="label mb-1">Correlation</div>
          <div className="overflow-x-auto">
            <table className="text-2xs font-mono num">
              <thead>
                <tr>
                  <th className="px-1"></th>
                  {d.tickers.map((t) => (
                    <th key={t} className="px-1 text-fg-secondary">{t}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.tickers.map((row) => (
                  <tr key={row}>
                    <td className="px-1 text-fg-secondary">{row}</td>
                    {d.tickers.map((col) => {
                      const v = d.correlations?.[row]?.[col] ?? 0;
                      const tone =
                        row === col ? "text-fg-muted"
                        : v > 0.6 ? "text-accent-short"
                        : v < -0.3 ? "text-accent-long"
                        : "text-fg-secondary";
                      return (
                        <td key={col} className={`px-1 ${tone}`}>{v.toFixed(2)}</td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone, sub }: { label: string; value: string; tone?: string; sub?: string }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className={`font-mono num text-sm mt-0.5 ${tone ?? "text-fg-primary"}`}>{value}</div>
      {sub && <div className="text-2xs text-fg-muted">{sub}</div>}
    </div>
  );
}
