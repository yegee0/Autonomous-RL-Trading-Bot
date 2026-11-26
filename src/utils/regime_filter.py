"""Chunk a price frame into regime-labelled segments.

Used by the training pipeline: one call returns the sub-frames that match
``regime`` (trend / range / crisis). Each sub-frame has ≥ ``min_len`` bars so
the policy sees enough context to learn.

The labels use the same thresholds as ``src.agents.ensemble.classify_regime``
so training distribution matches inference routing.
"""
from __future__ import annotations

import os
from typing import Iterable, List, Optional

import numpy as np
import pandas as pd


ROLL_WINDOW = int(os.getenv("REGIME_FILTER_WINDOW", 60))
MIN_SEGMENT = int(os.getenv("REGIME_MIN_SEGMENT", 80))

TREND_ADX = float(os.getenv("REGIME_TREND_ADX", 25.0))
RANGE_ADX = float(os.getenv("REGIME_RANGE_ADX", 18.0))
CRISIS_ATR_PCT = float(os.getenv("REGIME_CRISIS_ATR_PCT", 0.025))
CRISIS_DD = float(os.getenv("REGIME_CRISIS_DD", -0.10))


def _rolling_adx(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Compute ADX as a time series (classify_regime only gave scalar)."""
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
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window).mean() / atr)
    minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(window).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(window).mean()


def label_bars(df: pd.DataFrame) -> pd.Series:
    """Per-bar regime label: 'trend' | 'range' | 'crisis'."""
    if "ATR" not in df.columns:
        raise ValueError("df must have ATR column (run add_advanced_indicators first)")

    close = df["Close"]
    atr_pct = (df["ATR"] / close).fillna(0)

    peak = close.cummax()
    drawdown = (close - peak) / peak
    rolling_dd = drawdown.rolling(ROLL_WINDOW).min().fillna(0)

    adx = _rolling_adx(df)

    labels = pd.Series(index=df.index, dtype="object")
    # Crisis dominates — pick first.
    crisis_mask = (atr_pct >= CRISIS_ATR_PCT) | (rolling_dd <= CRISIS_DD)
    labels[crisis_mask] = "crisis"
    labels[~crisis_mask & (adx >= TREND_ADX)] = "trend"
    labels[~crisis_mask & (adx <= RANGE_ADX)] = "range"
    # Anything left (mid-ADX, non-crisis) → trend (neutral default).
    labels[labels.isna()] = "trend"
    return labels


def regime_segments(df: pd.DataFrame, regime: str, min_len: int = MIN_SEGMENT) -> List[pd.DataFrame]:
    """Return the sub-frames of df that match ``regime``, each ≥ ``min_len`` bars.

    Contiguous runs of the target regime are kept; short runs are padded with
    adjacent neutral bars so the policy still sees enough context.
    """
    if df is None or df.empty or regime == "all":
        return [df] if df is not None and not df.empty else []

    labels = label_bars(df)
    mask = labels == regime

    out: List[pd.DataFrame] = []
    in_run = False
    start = 0
    for i, flag in enumerate(mask.values):
        if flag and not in_run:
            start = i
            in_run = True
        elif not flag and in_run:
            end = i
            if end - start >= min_len:
                out.append(df.iloc[start:end].reset_index(drop=True))
            else:
                # pad a small run with ± min_len/2 context
                pad = min_len // 2
                lo = max(0, start - pad)
                hi = min(len(df), end + pad)
                if hi - lo >= min_len:
                    out.append(df.iloc[lo:hi].reset_index(drop=True))
            in_run = False
    if in_run and len(df) - start >= min_len:
        out.append(df.iloc[start:].reset_index(drop=True))
    return out


def filter_frames(
    frames: dict,
    regime: str,
    min_len: int = MIN_SEGMENT,
) -> dict:
    """Return a new dict keyed by `{original_key}#seg{n}` holding only matching segments.

    Crisis-period labelled frames (key starts with 'crisis:') pass through as-is
    for the 'crisis' and 'all' regimes — they're already in the right regime.
    """
    if regime == "all":
        return dict(frames)

    out: dict = {}
    for key, df in frames.items():
        # Crisis-period explicit frames always count toward 'crisis'.
        if key.startswith("crisis:") and regime == "crisis":
            out[key] = df
            continue
        if key.startswith("crisis:") and regime != "crisis":
            # Skip crisis periods for non-crisis heads.
            continue

        segments = regime_segments(df, regime, min_len=min_len)
        for i, seg in enumerate(segments):
            if "sentiment" not in seg.columns:
                seg = seg.copy()
                seg["sentiment"] = 0.0
            out[f"{key}#{regime}#seg{i}"] = seg
    return out
