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

from src.agents.rl_agent import calculate_fallback_signal, get_ai_action, load_agent  # noqa: E402
from src.agents.market_intelligence import MarketIntelligence  # noqa: E402
from src.utils.technical_indicators import add_advanced_indicators  # noqa: E402
from src.utils.risk_manager import calculate_position_sizing, calculate_risk_metrics  # noqa: E402

from backend.app.schemas.market import (
    Candle,
    Indicators,
    NewsItem,
    PositionSizing,
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
    )


def compute_signal(ticker: str, df: pd.DataFrame, sentiment: float) -> SignalResponse:
    if df is None or df.empty:
        raise ValueError(f"No usable data to score signal for {ticker}")
    current_price = float(df.iloc[-1]["Close"])
    model, _ = load_agent(ticker)
    source = "ppo" if model else "fallback"

    if model:
        try:
            action, confidence = get_ai_action(ticker, current_price, sentiment)
        except Exception as e:
            print(f"[signal] PPO inference failed, falling back: {e}")
            action, confidence = calculate_fallback_signal(df, sentiment)
            source = "fallback"
    else:
        action, confidence = calculate_fallback_signal(df, sentiment)

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


def fetch_news(ticker: str, limit: int = 8) -> tuple[List[NewsItem], float]:
    intel = get_intel()
    social = intel.get_social_intelligence(ticker)
    items = social.get("financial_news", [])[:limit]
    news = [
        NewsItem(
            title=n.get("title", ""),
            source=n.get("source", ""),
            link=n.get("link", ""),
            sentiment=float(n.get("sentiment", 0.0)),
            time_ago=n.get("date"),
        )
        for n in items
    ]
    avg = sum(n.sentiment for n in news) / len(news) if news else 0.0
    return news, avg
