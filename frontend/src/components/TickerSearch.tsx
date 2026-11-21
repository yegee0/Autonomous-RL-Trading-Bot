import { useEffect, useMemo, useRef, useState } from "react";
import { Search, Cpu } from "lucide-react";
import type { TickerMeta } from "../lib/types";

interface Props {
  tickers: TickerMeta[];
  value: string;
  onChange: (next: string) => void;
}

export function TickerSearch({ tickers, value, onChange }: Props) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);

  const matches = useMemo(() => {
    const q = query.toUpperCase().trim();
    if (!q) return tickers.slice(0, 8);
    return tickers
      .filter((t) => t.symbol.includes(q) || t.name.toUpperCase().includes(q))
      .slice(0, 8);
  }, [query, tickers]);

  function commit(symbol: string) {
    onChange(symbol);
    setQuery(symbol);
    setOpen(false);
  }

  return (
    <div ref={wrapRef} className="relative w-full sm:w-72 min-w-0">
      <div className="flex items-center gap-2 h-9 px-3 bg-bg-panel border border-line rounded focus-within:border-line-strong">
        <Search size={14} className="text-fg-muted shrink-0" />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value.toUpperCase());
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) commit(query.trim().toUpperCase());
          }}
          placeholder="Search ticker (BTC-USD, AAPL…)"
          className="flex-1 bg-transparent outline-none text-sm font-mono num text-fg-primary placeholder:text-fg-muted"
        />
      </div>

      {open && matches.length > 0 && (
        <ul className="absolute top-full left-0 right-0 mt-1 panel py-1 max-h-80 overflow-y-auto z-30">
          {matches.map((t) => (
            <li
              key={t.symbol}
              onClick={() => commit(t.symbol)}
              className="px-3 py-2 flex items-center justify-between cursor-pointer panel-hover"
            >
              <div className="min-w-0">
                <div className="font-mono text-sm text-fg-primary">{t.symbol}</div>
                <div className="text-2xs text-fg-muted truncate">{t.name}</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-2xs uppercase tracking-wider text-fg-muted">
                  {t.asset_class}
                </span>
                {t.model_available && <Cpu size={12} className="text-accent-long" />}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
