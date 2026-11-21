import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useLiveKline } from "../hooks/useLiveKline";
import { TIMEFRAMES, TopNav } from "../components/TopNav";
import { PriceHeader } from "../components/PriceHeader";
import { Chart } from "../components/Chart";
import { SignalCard } from "../components/SignalCard";
import { RiskPanel } from "../components/RiskPanel";
import { IndicatorStrip } from "../components/IndicatorStrip";
import { NewsStrip } from "../components/NewsStrip";
import { PanelSkeleton, Skeleton } from "../components/Skeleton";
import { BacktestPanel } from "../components/BacktestPanel";
import { PaperPanel } from "../components/PaperPanel";

type RailTab = "signal" | "paper" | "backtest";
const TABS: { id: RailTab; label: string }[] = [
  { id: "signal", label: "Signal" },
  { id: "paper", label: "Paper" },
  { id: "backtest", label: "Backtest" },
];

export function Dashboard() {
  const [ticker, setTicker] = useState("BTC-USD");
  const [tfId, setTfId] = useState("1M");
  const [railTab, setRailTab] = useState<RailTab>("signal");
  const [showMarkers, setShowMarkers] = useState(false);

  const tf = useMemo(() => TIMEFRAMES.find((t) => t.id === tfId) ?? TIMEFRAMES[2], [tfId]);

  const tickersQuery = useQuery({
    queryKey: ["tickers"],
    queryFn: api.tickers,
    staleTime: 60_000,
  });

  const analyzeQuery = useQuery({
    queryKey: ["analyze", ticker, tf.period, tf.interval],
    queryFn: () => api.analyze(ticker, tf.period, tf.interval),
    retry: 1,
    staleTime: 30_000,
  });

  const newsQuery = useQuery({
    queryKey: ["news", ticker],
    queryFn: () => api.news(ticker, 8),
    retry: 0,
    staleTime: 5 * 60_000,
  });

  const markersQuery = useQuery({
    queryKey: ["markers", ticker, tf.period, tf.interval],
    queryFn: () => api.signalHistory(ticker, tf.period, tf.interval, 200),
    enabled: showMarkers,
    staleTime: 2 * 60_000,
  });

  const isCrypto = ticker.endsWith("-USD");
  const { kline, connected } = useLiveKline(ticker, isCrypto);

  const data = analyzeQuery.data;
  const meta = tickersQuery.data?.find((t) => t.symbol === ticker);

  const change24h = useMemo(() => {
    if (!data?.candles?.length) return 0;
    const n = data.candles.length;
    const lastClose = kline?.close ?? data.candles[n - 1].close;
    const prev = data.candles[Math.max(0, n - 2)].close;
    return prev ? (lastClose - prev) / prev : 0;
  }, [data, kline]);

  const livePrice = kline?.close ?? data?.price ?? 0;

  return (
    <div className="h-full flex flex-col">
      <TopNav
        tickers={tickersQuery.data ?? []}
        ticker={ticker}
        onTicker={setTicker}
        timeframe={tfId}
        onTimeframe={setTfId}
        connected={connected}
      />

      <main className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4 p-4 overflow-y-auto">
        <section className="min-w-0 flex flex-col gap-4">
          {data ? (
            <PriceHeader meta={meta} ticker={ticker} price={livePrice} change24h={change24h} />
          ) : (
            <div className="panel px-5 py-4 flex items-center justify-between">
              <Skeleton height="1.25rem" width="180px" />
              <Skeleton height="1.75rem" width="140px" />
            </div>
          )}

          <div className="panel flex-1 min-h-[360px] relative overflow-hidden">
            {analyzeQuery.isLoading && (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-fg-muted">
                Loading market data…
              </div>
            )}
            {analyzeQuery.isError && (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-accent-short">
                No data for this ticker.
              </div>
            )}
            {data && (
              <Chart
                candles={data.candles}
                live={isCrypto ? kline : null}
                markers={showMarkers ? markersQuery.data ?? [] : []}
              />
            )}
            <button
              onClick={() => setShowMarkers((v) => !v)}
              className={`absolute top-3 right-3 z-10 btn-ghost ${
                showMarkers ? "text-accent-long" : ""
              }`}
            >
              {showMarkers ? "Hide signals" : "Show signals"}
            </button>
          </div>

          {data ? (
            <IndicatorStrip indicators={data.indicators} />
          ) : (
            <div className="panel px-4 py-3 grid grid-cols-3 sm:grid-cols-6 gap-x-6 gap-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i}>
                  <Skeleton height="0.75rem" width="40%" />
                  <div className="h-1" />
                  <Skeleton height="1rem" width="60%" />
                </div>
              ))}
            </div>
          )}

          <NewsStrip
            news={newsQuery.data ?? []}
            loading={newsQuery.isLoading}
            error={newsQuery.isError}
          />
        </section>

        <aside className="flex flex-col gap-4 min-w-0">
          <div className="flex gap-0.5 p-0.5 bg-bg-panel border border-line rounded-md">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setRailTab(t.id)}
                className={`flex-1 h-7 text-2xs uppercase tracking-wider rounded transition-colors ${
                  railTab === t.id
                    ? "bg-bg-hover text-fg-primary"
                    : "text-fg-secondary hover:text-fg-primary"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {data ? (
            <>
              {railTab === "signal" && (
                <>
                  <SignalCard signal={data.signal} price={livePrice} />
                  <RiskPanel risk={data.risk} sizing={data.sizing} />
                </>
              )}
              {railTab === "paper" && <PaperPanel ticker={ticker} livePrice={livePrice} />}
              {railTab === "backtest" && <BacktestPanel ticker={ticker} />}
            </>
          ) : (
            <>
              <PanelSkeleton rows={4} />
              <PanelSkeleton rows={6} />
            </>
          )}
        </aside>
      </main>
    </div>
  );
}
