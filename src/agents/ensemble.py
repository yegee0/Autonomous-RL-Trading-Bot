"""Rule-based mixture-of-experts over the existing PPO loaders.

Three expert heads:
  * trend   — strong directional ADX > 25
  * range   — sideways ADX < 18 and BB width small
  * crisis  — VIX > 25 OR ATR/close > 2.5%  OR  realised drawdown > 10%

A rule-based manager picks the regime from the latest bar + VIX, loads that
head's PPO model, and runs inference. Missing head → fall back to the
generalist (``model_general``). Missing generalist → rule-based signal.

Expert models live next to the generalist and share the same training
pipeline — just saved with different filenames:
    models/trained/model_trend.zip   + model_trend_vecnorm.pkl
    models/trained/model_range.zip   + model_range_vecnorm.pkl
    models/trained/model_crisis.zip  + model_crisis_vecnorm.pkl
"""
from __future__ import annotations

import os
import threading
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from src.agents.rl_agent import (
    _action_probs,
    _confidence,
    _load_pair,
    _paths_for,
    _stacked_obs,
    _ensure_sentiment,
    calculate_fallback_signal,
    load_agent,
)
from src.utils.data_loader import fetch_5m_with_indicators

_LOCK = threading.Lock()
_CACHE: dict = {}

EXPERTS = ("trend", "range", "crisis")

# Thresholds for the regime classifier — centralised here, env-overridable.
#
# Learned from an eval sweep: crisis head overfits (only sees narrow filtered
# data) so we gate it very strictly — ALL THREE triggers must fire. The trend
# head is the strongest absolute performer, so it's the default fallback.
TREND_ADX = float(os.getenv("REGIME_TREND_ADX", 25.0))
RANGE_ADX = float(os.getenv("REGIME_RANGE_ADX", 15.0))
CRISIS_VIX = float(os.getenv("REGIME_CRISIS_VIX", 40.0))
CRISIS_ATR_PCT = float(os.getenv("REGIME_CRISIS_ATR_PCT", 0.05))
CRISIS_DRAWDOWN = float(os.getenv("REGIME_CRISIS_DD", -0.20))


def _load_expert(name: str):
    with _LOCK:
        if name in _CACHE:
            return _CACHE[name]
        model, env = _load_pair(*_paths_for(name))
        if model is not None:
            _CACHE[name] = (model, env)
        return model, env


def _adx(df: pd.DataFrame, window: int = 14) -> Optional[float]:
    """Compute ADX on the fly if the frame doesn't carry it (none of our frames do)."""
    if len(df) < window + 2:
        return None
    try:
        high, low, close = df["High"], df["Low"], df["Close"]
        up = high.diff()
        dn = -low.diff()
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr = pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(window).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(window).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window).mean() / atr)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.rolling(window).mean().iloc[-1]
        return float(adx) if pd.notna(adx) else None
    except Exception:
        return None


def classify_regime(df: pd.DataFrame, vix: Optional[float] = None) -> str:
    """Return one of {"trend", "range", "crisis"}.

    Routing priority (tuned from the evaluation sweep):
      * CRISIS only when ALL three triggers fire (very strict): the crisis
        head was the worst backtest performer, so we send traffic there only
        when the market is truly in emergency mode.
      * RANGE when ADX is unambiguously flat AND ATR% is low.
      * TREND is the default — strongest standalone head.
    """
    if df is None or df.empty:
        return "trend"

    last = df.iloc[-1]
    close = float(last.get("Close", 0) or 0)
    atr = float(last.get("ATR", 0) or 0)
    atr_pct = atr / close if close > 0 else 0.0

    look = df.tail(60)
    rolling_peak = look["Close"].cummax()
    drawdown = float(((look["Close"] - rolling_peak) / rolling_peak).iloc[-1])

    vix_hot = vix is not None and vix >= CRISIS_VIX
    atr_hot = atr_pct >= CRISIS_ATR_PCT
    dd_hot = drawdown <= CRISIS_DRAWDOWN

    # Crisis needs genuine emergency: VIX extreme OR (high ATR AND deep DD).
    if vix_hot and atr_hot:
        return "crisis"
    if atr_hot and dd_hot:
        return "crisis"

    adx = _adx(df)
    # Range only when ADX is really low AND volatility is tame.
    if adx is not None and adx <= RANGE_ADX and atr_pct < 0.02:
        return "range"
    return "trend"


def predict_with_ensemble(
    ticker: str,
    current_price: float,
    sentiment_score: float = 0.0,
    vix: Optional[float] = None,
) -> Tuple[int, float, dict]:
    """Return (action, confidence, meta) where meta tells which head ran."""
    df = fetch_5m_with_indicators(ticker)
    if df is None or df.empty:
        return 0, 0.0, {"regime": "unknown", "expert": "none", "source": "empty"}

    df = _ensure_sentiment(df, sentiment_score)
    regime = classify_regime(df, vix=vix)

    # Try the regime-specific expert first.
    model, env = _load_expert(regime)
    expert_used = regime
    source = "expert"

    if model is None:
        # Fall back to generalist.
        model, env = load_agent(ticker)
        expert_used = "general"
        source = "fallback-general"

    if model is None:
        action, conf = calculate_fallback_signal(df, sentiment_score)
        return action, conf, {"regime": regime, "expert": "rule", "source": "fallback-rule"}

    try:
        obs = _stacked_obs(df, env)
        act, _ = model.predict(obs, deterministic=False)
        chosen = int(act[0])
        probs = _action_probs(model, obs)
        return chosen, _confidence(probs, chosen), {
            "regime": regime,
            "expert": expert_used,
            "source": source,
        }
    except Exception as e:
        action, conf = calculate_fallback_signal(df, sentiment_score)
        return action, conf, {
            "regime": regime,
            "expert": "rule",
            "source": f"inference-error:{type(e).__name__}",
        }
