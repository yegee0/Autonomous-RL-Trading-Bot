"""Thin service layer that wraps existing src/ modules into typed responses."""
from __future__ import annotations

import os
import sys
from typing import List, Optional

import pandas as pd
import yfinance as yf

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.agents.rl_agent import calculate_fallback_signal  # noqa: E402
from src.agents.ensemble import predict_with_ensemble  # noqa: E402
from src.agents.market_intelligence import MarketIntelligence  # noqa: E402
from src.utils.risk_manager import calculate_position_sizing, calculate_risk_metrics  # noqa: E402

from backend.app.schemas.market import (
    Candle,
    Fundamentals,
    Indicators,
    MacroMetric,
    MacroSnapshot,
    NewsFeed,
    NewsItem,
    PositionSizing,
    RedditPost,
    RiskMetrics,
    SignalResponse,
)

ACTION_LABELS = ["HOLD", "BUY_25", "BUY_50", "BUY_100", "SELL_25", "SELL_50", "SELL_100"]

_intel_singleton: Optional[MarketIntelligence] = None


def get_intel() -> MarketIntelligence:
    global _intel_singleton
    if _intel_singleton is None:
        _intel_singleton = MarketIntelligence()
    return _intel_singleton


def fetch_price_df(ticker: str, period: str = "3mo", interval: str = "1d") -> Optional[pd.DataFrame]:
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
    except Exception as e:
        print(f"[market] yfinance error: {e}")
        return None

    if data is None or data.empty:
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.reset_index()
    if "Datetime" in data.columns:
        data = data.rename(columns={"Datetime": "Date"})
    return data


def df_to_candles(df: pd.DataFrame, limit: int = 400) -> List[Candle]:
    if df is None or df.empty:
        return []
    tail = df.tail(limit)
    out: List[Candle] = []
    for _, row in tail.iterrows():
        ts = row.get("Date")
        if isinstance(ts, pd.Timestamp):
            unix = int(ts.timestamp())
        else:
            unix = int(pd.Timestamp(ts).timestamp())
        out.append(
            Candle(
                time=unix,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0.0)),
            )
        )
    return out


def extract_indicators(df: pd.DataFrame) -> Indicators:
    if df is None or df.empty:
        return Indicators()
    last = df.iloc[-1]

    def pick(name: str) -> Optional[float]:
        val = last.get(name)
        if val is None or pd.isna(val):
            return None
        return float(val)

    return Indicators(
        rsi=pick("RSI"),
        macd=pick("MACD"),
        macd_signal=pick("MACD_SIGNAL"),
        atr=pick("ATR"),
        sma20=pick("SMA20"),
        sma50=pick("SMA50"),
        bb_upper=pick("BB_Upper"),
        bb_lower=pick("BB_Lower"),
        stoch_k=pick("Stoch_K"),
        stoch_d=pick("Stoch_D"),
        volume_ratio=pick("Volume_Ratio"),
    )


def compute_signal(ticker: str, df: pd.DataFrame, sentiment: float) -> SignalResponse:
    if df is None or df.empty:
        raise ValueError(f"No usable data to score signal for {ticker}")
    current_price = float(df.iloc[-1]["Close"])

    # Pull VIX for the regime classifier. Cheap — cached inside MarketIntelligence.
    vix = None
    try:
        macro = get_intel().get_macro_data() or {}
        vix_entry = macro.get("VIX")
        if vix_entry:
            vix = float(vix_entry.get("val"))
    except Exception:
        vix = None

    try:
        action, confidence, meta = predict_with_ensemble(
            ticker, current_price, sentiment, vix=vix
        )
        source_raw = meta.get("source", "")
        regime = meta.get("regime")
        expert = meta.get("expert")
        if expert and expert != "rule":
            source = "ensemble"
        elif "rule" in source_raw:
            source = "fallback"
        else:
            source = "ppo"
    except Exception as e:
        print(f"[signal] ensemble failed, hard fallback: {e}")
        action, confidence = calculate_fallback_signal(df, sentiment)
        regime, expert, source = None, None, "fallback"

    action = int(action)
    direction = "long" if action in (1, 2, 3) else "short" if action in (4, 5, 6) else "flat"

    return SignalResponse(
        ticker=ticker,
        action=action,
        action_label=ACTION_LABELS[action],
        confidence=float(confidence),
        direction=direction,
        source=source,
        sentiment=float(sentiment),
        price=current_price,
        regime=regime,
        expert=expert,
    )


def compute_risk(df: pd.DataFrame) -> RiskMetrics:
    metrics = calculate_risk_metrics(df)
    return RiskMetrics(**{k: float(v) for k, v in metrics.items()})


def compute_sizing(df: pd.DataFrame, balance: float, confidence: float) -> PositionSizing:
    s = calculate_position_sizing(df, balance, confidence=confidence)
    if not s:
        return PositionSizing()
    return PositionSizing(
        position_size_usd=float(s.get("position_size_usd", 0.0)),
        position_size_pct=float(s.get("position_size_pct", 0.0)),
        stop_loss=float(s.get("stop_loss", 0.0)),
        take_profit=float(s.get("take_profit", 0.0)),
        kelly_fraction=float(s.get("kelly_fraction", 0.0)),
    )


def fetch_news(ticker: str, limit: int = 8, include_reddit: bool = True) -> NewsFeed:
    intel = get_intel()
    social = intel.get_social_intelligence(ticker, include_reddit=include_reddit)

    news_items = social.get("financial_news", [])[:limit]
    news = [
        NewsItem(
            title=n.get("title", ""),
            source=n.get("source", ""),
            link=n.get("link", ""),
            sentiment=float(n.get("sentiment", 0.0)),
            time_ago=n.get("date") or None,
        )
        for n in news_items
    ]

    reddit_items = social.get("reddit_posts", [])[:limit]
    reddit = [
        RedditPost(
            title=r.get("title", ""),
            body=r.get("body", ""),
            score=int(r.get("score", 0)),
            comments=int(r.get("comments", 0)),
            sub=r.get("sub", ""),
            link=r.get("link", ""),
            sentiment=float(r.get("sentiment", 0.0)),
            time_ago=r.get("time_ago") or None,
        )
        for r in reddit_items
    ]

    pool = [n.sentiment for n in news] + [r.sentiment for r in reddit]
    avg = sum(pool) / len(pool) if pool else 0.0
    return NewsFeed(news=news, reddit=reddit, avg_sentiment=float(avg))


_FUNDAMENTAL_FIELDS = {
    "market_cap", "trailing_pe", "forward_pe", "price_to_book",
    "profit_margin", "roe", "revenue", "revenue_growth",
    "earnings_growth", "dividend_yield", "beta", "target_mean",
}


def _coerce_optional_float(val):
    try:
        if val is None or val == "N/A":
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def fetch_fundamentals(ticker: str) -> Fundamentals:
    intel = get_intel()
    raw = intel.get_comprehensive_fundamentals(ticker) or {}
    is_crypto = "-USD" in ticker or "-USDT" in ticker

    # The raw dict uses legacy keys (e.g. "52_week_high") — remap into the schema.
    data = dict(raw)
    data["fifty_two_week_high"] = raw.get("52_week_high")
    data["fifty_two_week_low"] = raw.get("52_week_low")

    for f in _FUNDAMENTAL_FIELDS:
        if f in data:
            data[f] = _coerce_optional_float(data[f])
    data["fifty_two_week_high"] = _coerce_optional_float(data.get("fifty_two_week_high"))
    data["fifty_two_week_low"] = _coerce_optional_float(data.get("fifty_two_week_low"))
    rec = data.get("recommendation")
    data["recommendation"] = str(rec) if rec and rec != "N/A" else None

    allowed = Fundamentals.model_fields.keys()
    filtered = {k: v for k, v in data.items() if k in allowed}
    filtered["is_crypto"] = is_crypto
    return Fundamentals(**filtered)


def fetch_macro_snapshot() -> MacroSnapshot:
    intel = get_intel()
    macro = intel.get_macro_data() or {}
    fg = intel.get_fear_greed_index() or {}

    def _metric(key: str):
        m = macro.get(key)
        if not m:
            return None
        return MacroMetric(value=float(m.get("val", 0.0)), delta=float(m.get("delta", 0.0)))

    return MacroSnapshot(
        vix=_metric("VIX"),
        us10y=_metric("US10Y"),
        dxy=_metric("DXY"),
        fear_greed=float(fg["score"]) if "score" in fg else None,
        fear_greed_label=fg.get("label"),
    )
