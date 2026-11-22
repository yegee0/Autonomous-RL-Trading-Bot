import { useMemo, useState } from "react";
import { ExternalLink, MessageSquare, TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { NewsFeed } from "../lib/types";

interface Props {
  feed?: NewsFeed;
  loading?: boolean;
  error?: boolean;
}

type Tab = "news" | "reddit";

export function NewsStrip({ feed, loading, error }: Props) {
  const [tab, setTab] = useState<Tab>("news");

  const newsCount = feed?.news.length ?? 0;
  const redditCount = feed?.reddit.length ?? 0;

  const avgSentiment = feed?.avg_sentiment ?? 0;

  const sentimentTone = useMemo(() => {
    if (avgSentiment > 0.15) return { text: "Bullish", cls: "text-accent-long", Icon: TrendingUp };
    if (avgSentiment < -0.15) return { text: "Bearish", cls: "text-accent-short", Icon: TrendingDown };
    return { text: "Neutral", cls: "text-fg-secondary", Icon: Minus };
  }, [avgSentiment]);

  if (loading) {
    return <div className="panel p-6 text-fg-muted text-sm text-center">Loading sentiment feed…</div>;
  }
  if (error) {
    return <div className="panel p-6 text-fg-muted text-sm text-center">Feed unavailable.</div>;
  }
  if (!feed || (newsCount === 0 && redditCount === 0)) {
    return <div className="panel p-6 text-fg-muted text-sm text-center">No recent chatter.</div>;
  }

  return (
    <div className="panel">
      <div className="hairline px-4 py-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <TabBtn active={tab === "news"} onClick={() => setTab("news")} count={newsCount}>
            Headlines
          </TabBtn>
          <TabBtn active={tab === "reddit"} onClick={() => setTab("reddit")} count={redditCount}>
            Reddit
          </TabBtn>
        </div>
        <div className={`flex items-center gap-1.5 text-2xs ${sentimentTone.cls}`}>
          <sentimentTone.Icon size={12} />
          <span className="uppercase tracking-wider">{sentimentTone.text}</span>
          <span className="font-mono num">
            {avgSentiment >= 0 ? "+" : ""}
            {avgSentiment.toFixed(2)}
          </span>
        </div>
      </div>

      {tab === "news" && (
        <ul>
          {feed.news.map((n, i) => {
            const tone =
              n.sentiment > 0.1
                ? "border-l-accent-long"
                : n.sentiment < -0.1
                ? "border-l-accent-short"
                : "border-l-fg-dim";
            return (
              <li
                key={`n-${i}`}
                className={`flex items-center justify-between gap-4 px-4 py-2.5 border-l-2 ${tone} border-b border-line last:border-b-0 panel-hover`}
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-fg-primary truncate">{n.title}</div>
                  <div className="text-2xs text-fg-muted mt-0.5 flex items-center gap-2">
                    <span>{n.source}</span>
                    {n.time_ago && <span>• {n.time_ago}</span>}
                    <span className="font-mono num">
                      sent {n.sentiment >= 0 ? "+" : ""}
                      {n.sentiment.toFixed(2)}
                    </span>
                  </div>
                </div>
                {n.link && (
                  <a
                    href={n.link}
                    target="_blank"
                    rel="noreferrer"
                    className="btn-ghost shrink-0"
                    aria-label="Open article"
                  >
                    <ExternalLink size={12} />
                  </a>
                )}
              </li>
            );
          })}
          {feed.news.length === 0 && (
            <li className="px-4 py-6 text-center text-xs text-fg-muted">No headlines right now.</li>
          )}
        </ul>
      )}

      {tab === "reddit" && (
        <ul>
          {feed.reddit.map((r, i) => {
            const tone =
              r.sentiment > 0.1
                ? "border-l-accent-long"
                : r.sentiment < -0.1
                ? "border-l-accent-short"
                : "border-l-fg-dim";
            return (
              <li
                key={`r-${i}`}
                className={`flex items-center justify-between gap-4 px-4 py-2.5 border-l-2 ${tone} border-b border-line last:border-b-0 panel-hover`}
              >
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-fg-primary truncate">{r.title}</div>
                  <div className="text-2xs text-fg-muted mt-0.5 flex items-center gap-2 flex-wrap">
                    <span className="text-accent-info">r/{r.sub}</span>
                    {r.time_ago && <span>• {r.time_ago}</span>}
                    <span className="font-mono num">▲ {r.score}</span>
                    <span className="font-mono num flex items-center gap-0.5">
                      <MessageSquare size={10} />
                      {r.comments}
                    </span>
                    <span className="font-mono num">
                      sent {r.sentiment >= 0 ? "+" : ""}
                      {r.sentiment.toFixed(2)}
                    </span>
                  </div>
                </div>
                {r.link && (
                  <a
                    href={r.link}
                    target="_blank"
                    rel="noreferrer"
                    className="btn-ghost shrink-0"
                    aria-label="Open thread"
                  >
                    <ExternalLink size={12} />
                  </a>
                )}
              </li>
            );
          })}
          {feed.reddit.length === 0 && (
            <li className="px-4 py-6 text-center text-xs text-fg-muted">
              No matching Reddit chatter this week.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function TabBtn({
  children,
  active,
  onClick,
  count,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
  count: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 text-2xs uppercase tracking-wider transition-colors ${
        active ? "text-fg-primary" : "text-fg-muted hover:text-fg-secondary"
      }`}
    >
      {children}
      <span
        className={`font-mono num px-1.5 py-0.5 rounded ${
          active ? "bg-bg-hover text-fg-secondary" : "bg-bg-panel2"
        }`}
      >
        {count}
      </span>
    </button>
  );
}
