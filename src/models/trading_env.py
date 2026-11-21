"""Scale-invariant single-asset trading environment.

Features are expressed as ratios so the same policy generalises across BTC
at $60,000 and AAPL at $200. Observation vector (shape 8):

    [ cash_ratio,         # cash / initial_balance             -> ~0..1
      position_ratio,     # shares*price / net_worth           -> 0..1
      ret_1,              # (close[t] - close[t-1]) / close[t-1]
      ret_5,              # (close[t] - close[t-5]) / close[t-5]
      rsi_norm,           # RSI / 100                          -> 0..1
      macd_hist_norm,     # (MACD - MACD_signal) / close       -> small
      atr_ratio,          # ATR / close                        -> small, >0
      sentiment ]         # [-1, 1]

Action space (Discrete 7, unchanged):
    0 hold | 1 buy 25% | 2 buy 50% | 3 buy 100%
    4 sell 25% | 5 sell 50% | 6 sell 100%
"""
from __future__ import annotations

import math
from typing import Optional

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

OBS_DIM = 8
INITIAL_BALANCE = 10_000.0
COMMISSION = 0.001


def _safe(x: float, default: float = 0.0) -> float:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return default
    return float(x)


def build_observation(
    df: pd.DataFrame,
    idx: int,
    cash: float,
    shares: float,
    initial_balance: float = INITIAL_BALANCE,
) -> np.ndarray:
    """Pure helper used both by env and by inference-time code."""
    row = df.iloc[idx]
    close = _safe(row.get("Close"), 1.0) or 1.0
    close_1 = _safe(df.iloc[idx - 1]["Close"], close) if idx >= 1 else close
    close_5 = _safe(df.iloc[idx - 5]["Close"], close) if idx >= 5 else close

    ret_1 = (close - close_1) / close_1 if close_1 else 0.0
    ret_5 = (close - close_5) / close_5 if close_5 else 0.0
    rsi = _safe(row.get("RSI"), 50.0) / 100.0
    macd = _safe(row.get("MACD"), 0.0)
    macd_sig = _safe(row.get("MACD_SIGNAL"), 0.0)
    macd_hist_norm = (macd - macd_sig) / close if close else 0.0
    atr_ratio = _safe(row.get("ATR"), 0.0) / close if close else 0.0
    sentiment = _safe(row.get("sentiment"), 0.0)

    net_worth = cash + shares * close
    cash_ratio = cash / max(initial_balance, 1.0)
    position_ratio = (shares * close) / net_worth if net_worth > 0 else 0.0

    return np.array(
        [cash_ratio, position_ratio, ret_1, ret_5, rsi, macd_hist_norm, atr_ratio, sentiment],
        dtype=np.float32,
    )


class StockTradingEnv(gym.Env):
    """Single-asset environment. Multi-ticker training is handled by wrapping
    this with a dataset that swaps frames on ``reset``."""

    metadata = {"render_modes": []}

    def __init__(self, df: pd.DataFrame, initial_balance: float = INITIAL_BALANCE):
        super().__init__()
        if df is None or df.empty:
            raise ValueError("Empty dataframe passed to StockTradingEnv")
        self.df = df.reset_index(drop=True)
        self.initial_balance = float(initial_balance)

        self.action_space = spaces.Discrete(7)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32
        )

        self.max_steps = len(self.df) - 1
        self.current_step = 0
        self.balance = self.initial_balance
        self.shares_held = 0.0
        self.net_worth = self.initial_balance

    def swap_frame(self, df: pd.DataFrame) -> None:
        """Replace the underlying frame; useful for multi-ticker training."""
        if df is None or df.empty:
            raise ValueError("Cannot swap to an empty frame")
        self.df = df.reset_index(drop=True)
        self.max_steps = len(self.df) - 1

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        self.balance = self.initial_balance
        self.shares_held = 0.0
        self.current_step = 0
        self.net_worth = self.initial_balance
        return self._obs(), {}

    def _obs(self) -> np.ndarray:
        return build_observation(
            self.df,
            min(self.current_step, self.max_steps),
            self.balance,
            self.shares_held,
            self.initial_balance,
        )

    def step(self, action: int):
        idx = min(self.current_step, self.max_steps)
        row = self.df.iloc[idx]
        price = _safe(row.get("Close"), 1.0) or 1.0
        atr = _safe(row.get("ATR"), 0.0)

        if action in (1, 2, 3):
            frac = {1: 0.25, 2: 0.50, 3: 1.0}[action]
            spend = self.balance * frac
            if spend > 10:
                total = spend * (1.0 + COMMISSION)
                if self.balance >= total:
                    self.balance -= total
                    self.shares_held += spend / price
        elif action in (4, 5, 6):
            if self.shares_held > 0:
                frac = {4: 0.25, 5: 0.50, 6: 1.0}[action]
                shares_to_sell = self.shares_held * frac
                proceeds = shares_to_sell * price * (1.0 - COMMISSION)
                self.shares_held -= shares_to_sell
                self.balance += proceeds

        self.current_step += 1
        terminated = self.current_step >= self.max_steps

        next_idx = min(self.current_step, self.max_steps)
        next_price = _safe(self.df.iloc[next_idx].get("Close"), price) or price
        new_net_worth = self.balance + self.shares_held * next_price

        # Reward: fractional net-worth change (unit-free) minus holding-risk penalty.
        prev_nw = self.net_worth if self.net_worth > 0 else self.initial_balance
        pnl_pct = (new_net_worth - prev_nw) / prev_nw
        risk_penalty = (atr / price) * 0.1 if self.shares_held > 0 else 0.0
        reward = pnl_pct - risk_penalty

        self.net_worth = new_net_worth

        info = {"net_worth": float(self.net_worth), "price": float(next_price)}
        return self._obs(), float(reward), terminated, False, info
