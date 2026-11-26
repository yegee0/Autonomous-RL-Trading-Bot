import { useQuery } from "@tanstack/react-query";
import { CalendarClock, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";

interface Props {
  ticker: string;
}

export function CalendarCard({ ticker }: Props) {
  const q = useQuery({
    queryKey: ["calendar", ticker],
    queryFn: () => api.calendar(ticker, 168),
    refetchInterval: 5 * 60_000,
    retry: 0,
  });

  const d = q.data;

  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="label flex items-center gap-1.5">
          <CalendarClock size={12} />
          Economic calendar
        </span>
        {d?.event_window_active && (
          <span className="flex items-center gap-1 text-accent-neutral text-2xs uppercase tracking-wider">
            <AlertTriangle size={12} />
            event window
          </span>
        )}
      </div>

      {d?.event_window_active && d.active_event && (
        <div className="rounded border border-accent-neutral/30 bg-accent-neutral/10 p-2 text-xs">
          <div className="text-accent-neutral font-semibold">
            {d.active_event.name}
          </div>
          <div className="text-2xs text-fg-muted mt-0.5">
            New buys are blocked by the event-window guardrail.
          </div>
        </div>
      )}

      {!d && q.isLoading && <div className="text-xs text-fg-muted">Loading…</div>}
      {q.isError && <div className="text-xs text-accent-short">Unavailable.</div>}

      {d && d.events.length === 0 && (
        <div className="text-xs text-fg-muted">No high-impact events scheduled.</div>
      )}

      {d && d.events.length > 0 && (
        <ul className="space-y-1 max-h-72 overflow-y-auto">
          {d.events.slice(0, 15).map((e, i) => {
            const date = new Date(e.ts * 1000);
            const tone =
              e.impact === "high"
                ? "text-accent-short"
                : e.impact === "medium"
                ? "text-accent-neutral"
                : "text-fg-secondary";
            return (
              <li
                key={i}
                className="flex items-center justify-between text-xs border-b border-line last:border-b-0 py-1"
              >
                <div>
                  <div className="text-fg-primary">{e.name}</div>
                  <div className="text-2xs text-fg-muted">
                    {date.toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
                <span className={`text-2xs uppercase tracking-wider ${tone}`}>{e.impact}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
