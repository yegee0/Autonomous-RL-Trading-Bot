import { ExternalLink } from "lucide-react";
import type { NewsItem } from "../lib/types";

interface Props {
  news: NewsItem[];
  loading?: boolean;
  error?: boolean;
}

export function NewsStrip({ news, loading, error }: Props) {
  if (loading) {
    return (
      <div className="panel p-6 text-fg-muted text-sm text-center">Loading headlines…</div>
    );
  }
  if (error) {
    return (
      <div className="panel p-6 text-fg-muted text-sm text-center">Headlines unavailable.</div>
    );
  }
  if (!news.length) {
    return (
      <div className="panel p-6 text-fg-muted text-sm text-center">No recent headlines.</div>
    );
  }

  return (
    <div className="panel">
      <div className="hairline px-4 py-2 flex items-center justify-between">
        <span className="label">Headlines</span>
        <span className="text-2xs text-fg-muted">{news.length}</span>
      </div>
      <ul>
        {news.map((n, i) => {
          const tone =
            n.sentiment > 0.1
              ? "border-l-accent-long"
              : n.sentiment < -0.1
              ? "border-l-accent-short"
              : "border-l-fg-dim";
          return (
            <li
              key={i}
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
      </ul>
    </div>
  );
}
