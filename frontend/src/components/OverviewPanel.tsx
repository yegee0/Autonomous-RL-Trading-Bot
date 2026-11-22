import { ExternalLink } from "lucide-react";
import type { Fundamentals } from "../lib/types";
import { formatCompact, formatNum, formatPct } from "../lib/format";

interface Props {
  info?: Fundamentals;
  loading?: boolean;
}

export function OverviewPanel({ info, loading }: Props) {
  if (loading) {
    return (
      <div className="panel p-4 text-xs text-fg-muted">Loading fundamentals…</div>
    );
  }
  if (!info) return null;

  const isCrypto = info.is_crypto;

  return (
    <div className="panel p-4 flex flex-col gap-4">
      <div>
        <div className="flex items-center justify-between">
          <span className="label">About</span>
          {info.website && (
            <a
              href={info.website}
              target="_blank"
              rel="noreferrer"
              className="btn-ghost"
              aria-label="Open website"
            >
              <ExternalLink size={12} />
            </a>
          )}
        </div>
        <div className="text-sm text-fg-primary mt-1">{info.company_name ?? "—"}</div>
        {info.sector && (
          <div className="text-2xs text-fg-muted mt-0.5">
            {info.sector}
            {info.industry ? ` · ${info.industry}` : ""}
            {info.country ? ` · ${info.country}` : ""}
          </div>
        )}
        {info.description && (
          <p className="text-xs text-fg-secondary mt-2 leading-relaxed line-clamp-4">
            {info.description}
          </p>
        )}
      </div>

      {!isCrypto && (
        <>
          <div className="hairline -mx-4" />

          <div>
            <div className="label mb-2">Valuation</div>
            <Row k="Market Cap" v={info.market_cap != null ? `$${formatCompact(info.market_cap)}` : "—"} />
            <Row k="P/E (TTM)" v={formatNum(info.trailing_pe, 2)} />
            <Row k="P/E (fwd)" v={formatNum(info.forward_pe, 2)} />
            <Row k="P/B" v={formatNum(info.price_to_book, 2)} />
            <Row k="Beta" v={formatNum(info.beta, 2)} />
          </div>

          <div className="hairline -mx-4" />

          <div>
            <div className="label mb-2">Profitability</div>
            <Row k="Profit Margin" v={formatPct(info.profit_margin, 2)} />
            <Row k="ROE" v={formatPct(info.roe, 2)} />
            <Row k="Revenue" v={info.revenue != null ? `$${formatCompact(info.revenue)}` : "—"} />
            <Row k="Rev Growth" v={formatPct(info.revenue_growth, 2)} tone={deltaTone(info.revenue_growth)} />
            <Row k="EPS Growth" v={formatPct(info.earnings_growth, 2)} tone={deltaTone(info.earnings_growth)} />
            <Row k="Dividend" v={formatPct(info.dividend_yield, 2)} />
          </div>

          <div className="hairline -mx-4" />

          <div>
            <div className="label mb-2">Analyst</div>
            <Row k="Target" v={info.target_mean != null ? `$${formatNum(info.target_mean, 2)}` : "—"} />
            <Row k="Rec" v={info.recommendation ? info.recommendation.toUpperCase() : "—"} />
          </div>
        </>
      )}

      <div className="hairline -mx-4" />
      <div>
        <div className="label mb-2">Range</div>
        <Row k="52W High" v={info.fifty_two_week_high != null ? `$${formatNum(info.fifty_two_week_high, 2)}` : "—"} />
        <Row k="52W Low" v={info.fifty_two_week_low != null ? `$${formatNum(info.fifty_two_week_low, 2)}` : "—"} />
      </div>
    </div>
  );
}

function deltaTone(n: number | null | undefined): "long" | "short" | undefined {
  if (n == null) return undefined;
  if (n > 0) return "long";
  if (n < 0) return "short";
  return undefined;
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
