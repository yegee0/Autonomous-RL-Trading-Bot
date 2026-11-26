"""Shock-injection wrapper over StockTradingEnv.

At each step there's a small probability of overwriting the next bar with a
synthetic flash-crash:
    close *= (1 - 0.10..0.25)      # price crashes 10–25%
    high  = open; low = new close   # ugly red candle
    volume *= 5..15                # flight / forced selling

Teaches the policy that a sudden 15%+ drop IS a thing that happens, so it
doesn't go all-in just because the rolling vol looks low. Shocks are applied
in-place to the current frame copy so the reward/obs pipeline sees them
exactly as a real drop would.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.trading_env import StockTradingEnv


class CrisisWrapperEnv(StockTradingEnv):
    """Drop-in replacement for StockTradingEnv with stochastic flash crashes."""

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        shock_prob: float = 0.003,   # ~1 in 333 bars → a handful per year of 5m bars
        shock_min: float = 0.08,
        shock_max: float = 0.22,
        seed: int | None = None,
    ) -> None:
        super().__init__(df)
        self.shock_prob = float(shock_prob)
        self.shock_min = float(shock_min)
        self.shock_max = float(shock_max)
        self._rng = np.random.default_rng(seed)
        self._shocked_idx: set[int] = set()

    def reset(self, seed=None, options=None):
        self._shocked_idx.clear()
        return super().reset(seed=seed, options=options)

    def _maybe_shock(self, idx: int) -> None:
        if idx <= 0 or idx >= len(self.df) or idx in self._shocked_idx:
            return
        if self._rng.random() >= self.shock_prob:
            return
        self._shocked_idx.add(idx)

        magnitude = float(self._rng.uniform(self.shock_min, self.shock_max))
        row = self.df.iloc[idx].copy()
        prev_close = float(self.df.iloc[idx - 1]["Close"])
        new_close = prev_close * (1.0 - magnitude)

        self.df.at[idx, "Open"] = prev_close
        self.df.at[idx, "High"] = prev_close
        self.df.at[idx, "Low"] = new_close
        self.df.at[idx, "Close"] = new_close
        if "Volume" in self.df.columns:
            self.df.at[idx, "Volume"] = float(row.get("Volume", 0)) * float(
                self._rng.uniform(5.0, 15.0)
            )
        if "ATR" in self.df.columns:
            self.df.at[idx, "ATR"] = max(float(row.get("ATR", 0)), prev_close * 0.05)

    def step(self, action: int):
        self._maybe_shock(min(self.current_step + 1, self.max_steps))
        return super().step(action)
