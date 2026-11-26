"""Economic calendar + earnings + an event-window guardrail.

Two sources merged:
  1. Static table of major US macro releases (FOMC, CPI, NFP, PPI, Core PCE).
     These dates don't shift — Fed posts the year ahead. Baked into code so
     we never depend on scraping during a release window.
  2. yfinance ``Ticker.earnings_dates`` for stock-specific earnings calls.

An event is "active" from -30min to +30min of its scheduled time. The guardrail
calls ``in_event_window(ticker)`` and refuses new buys if True.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import yfinance as yf

log = logging.getLogger("calendar")


# Impact rating is the macro-event tier ("high" = market-moving).
# All times UTC.
_STATIC_MACRO_EVENTS: List[tuple] = [
    # (utc_iso, name, impact, affects: "all"|"crypto"|"stocks")
    # ---- 2025 (past) ----
    ("2025-01-29T19:00:00", "FOMC Rate Decision", "high", "all"),
    ("2025-02-12T13:30:00", "US CPI", "high", "all"),
    ("2025-03-07T13:30:00", "US NFP", "high", "all"),
    ("2025-03-19T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2025-05-07T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2025-06-18T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2025-07-30T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2025-09-17T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2025-10-29T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2025-12-10T19:00:00", "FOMC Rate Decision", "high", "all"),
    # ---- 2026 (upcoming — public Fed schedule) ----
    ("2026-01-28T19:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-02-11T13:30:00", "US CPI", "high", "all"),
    ("2026-02-06T13:30:00", "US NFP", "high", "all"),
    ("2026-03-04T13:30:00", "US ADP Employment", "medium", "all"),
    ("2026-03-11T13:30:00", "US CPI", "high", "all"),
    ("2026-03-18T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-04-10T13:30:00", "US CPI", "high", "all"),
    ("2026-04-29T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-05-08T13:30:00", "US NFP", "high", "all"),
    ("2026-06-17T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-07-29T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-09-16T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-10-28T18:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-11-05T13:30:00", "US NFP", "high", "all"),
    ("2026-11-12T13:30:00", "US CPI", "high", "all"),
    ("2026-11-26T13:30:00", "US Core PCE", "high", "all"),
    ("2026-12-04T13:30:00", "US NFP", "high", "all"),
    ("2026-12-09T19:00:00", "FOMC Rate Decision", "high", "all"),
    ("2026-12-10T13:30:00", "US CPI", "high", "all"),
    # ---- 2027 (forward schedule, Fed regular cadence) ----
    ("2027-01-08T13:30:00", "US NFP", "high", "all"),
    ("2027-01-13T13:30:00", "US CPI", "high", "all"),
    ("2027-01-27T19:00:00", "FOMC Rate Decision", "high", "all"),
    ("2027-02-05T13:30:00", "US NFP", "high", "all"),
    ("2027-02-10T13:30:00", "US CPI", "high", "all"),
    ("2027-03-10T13:30:00", "US CPI", "high", "all"),
    ("2027-03-17T18:00:00", "FOMC Rate Decision", "high", "all"),
]


@dataclass
class CalendarEvent:
    ts: int           # unix seconds UTC
    name: str
    impact: str       # "high" | "medium" | "low"
    affects: str      # "all" | "crypto" | "stocks" | <ticker>
    source: str       # "macro" | "earnings"


def _parse_static() -> List[CalendarEvent]:
    out: List[CalendarEvent] = []
    for iso, name, impact, affects in _STATIC_MACRO_EVENTS:
        try:
            dt = datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)
            out.append(
                CalendarEvent(
                    ts=int(dt.timestamp()),
                    name=name,
                    impact=impact,
                    affects=affects,
                    source="macro",
                )
            )
        except ValueError:
            continue
    return out


def _fetch_earnings(ticker: str) -> List[CalendarEvent]:
    """yfinance earnings_dates — best effort, silent on failure."""
    if "-USD" in ticker or ".IS" in ticker:
        return []  # crypto / BIST don't have US-style earnings calendar
    try:
        tk = yf.Ticker(ticker)
        df = tk.earnings_dates
        if df is None or df.empty:
            return []
    except Exception as e:
        log.debug("earnings fetch failed for %s: %s", ticker, e)
        return []

    out: List[CalendarEvent] = []
    for idx in df.index[:6]:
        try:
            dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            out.append(
                CalendarEvent(
                    ts=int(dt.timestamp()),
                    name=f"{ticker} Earnings",
                    impact="high",
                    affects=ticker.upper(),
                    source="earnings",
                )
            )
        except Exception:
            continue
    return out


def upcoming_events(
    ticker: Optional[str] = None,
    hours_ahead: int = 24 * 7,
    hours_back: int = 1,
) -> List[CalendarEvent]:
    """Return relevant events in the given window, sorted by time."""
    now_s = int(datetime.now(tz=timezone.utc).timestamp())
    lo = now_s - hours_back * 3600
    hi = now_s + hours_ahead * 3600

    out: List[CalendarEvent] = []
    for ev in _parse_static():
        if ev.ts < lo or ev.ts > hi:
            continue
        if ticker and ev.affects not in ("all",):
            if ev.affects == "stocks" and ("-USD" in ticker or ".IS" in ticker):
                continue
            if ev.affects == "crypto" and "-USD" not in ticker:
                continue
        out.append(ev)

    if ticker:
        for ev in _fetch_earnings(ticker):
            if lo <= ev.ts <= hi:
                out.append(ev)

    out.sort(key=lambda e: e.ts)
    return out


def in_event_window(
    ticker: Optional[str] = None,
    minutes_before: int = 30,
    minutes_after: int = 30,
) -> Optional[CalendarEvent]:
    """Return the event whose window currently includes 'now', else None."""
    now = int(datetime.now(tz=timezone.utc).timestamp())
    before = minutes_before * 60
    after = minutes_after * 60
    for ev in upcoming_events(ticker=ticker, hours_ahead=2, hours_back=2):
        if ev.impact != "high":
            continue
        if ev.ts - before <= now <= ev.ts + after:
            return ev
    return None
