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
from collections import deque
from typing import Optional

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

OBS_DIM = 8
INITIAL_BALANCE = 10_000.0

# ---- Trading cost model (per fill) ----
# COMMISSION: exchange/broker fee as a fraction of notional (10 bps).
# SPREAD_BPS: half of the bid/ask spread we cross — buys pay +, sells pay −.
# SLIPPAGE_BPS: additional impact that scales with order size vs ATR.
COMMISSION = 0.001           # 10 bps
SPREAD_BPS = 2.0             # 2 bps half-spread
SLIPPAGE_BPS_PER_ATR = 1.5   # multiplied by |frac| when size matters

# Risk-adjusted reward weights. Tunable without retraining old models —
# only affects training reward signal, not inference.
#
# Earlier version was too fearful (quadratic DD + ATR penalty every bar) which
# taught the policy to stay in cash through strong rallies. Rebalanced:
#   • DD penalty: linear instead of quadratic (deep DD still hurts, shallow DD is fine)
#   • Sharpe bonus: bumped up a little, rewards smooth equity curves
#   • Holding cost: only when actually long AND volatility is spiking
#   • Opportunity cost: tiny negative reward when flat during a visible uptrend
SHARPE_WINDOW = 20
SHARPE_WEIGHT = 0.10
DD_PENALTY = 0.25
HOLDING_PENALTY = 0.03      # fraction of ATR/price applied only when long
OPPORTUNITY_COST = 0.08     # fraction of positive 1-bar return when flat during an uptrend


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
        self.peak_net_worth = self.initial_balance
        self.ret_window: deque = deque(maxlen=SHARPE_WINDOW)

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
        self.peak_net_worth = self.initial_balance
        self.ret_window.clear()
        return self._obs(), {}

    @staticmethod
    def _fill_price(mid: float, atr: float, frac: float, side: str) -> float:
        """Apply spread + size-aware slippage. ``side`` is 'buy' or 'sell'."""
        spread = SPREAD_BPS / 10_000.0
        size_impact = (atr / max(mid, 1e-9)) * SLIPPAGE_BPS_PER_ATR * abs(frac) / 10.0
        bps = spread + size_impact
        return mid * (1.0 + bps if side == "buy" else 1.0 - bps)

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
                fill = self._fill_price(price, atr, frac, "buy")
                total = spend * (1.0 + COMMISSION)
                if self.balance >= total:
                    self.balance -= total
                    self.shares_held += spend / fill
        elif action in (4, 5, 6):
            if self.shares_held > 0:
                frac = {4: 0.25, 5: 0.50, 6: 1.0}[action]
                shares_to_sell = self.shares_held * frac
                fill = self._fill_price(price, atr, frac, "sell")
                proceeds = shares_to_sell * fill * (1.0 - COMMISSION)
                self.shares_held -= shares_to_sell
                self.balance += proceeds

        self.current_step += 1
        terminated = self.current_step >= self.max_steps

        next_idx = min(self.current_step, self.max_steps)
        next_price = _safe(self.df.iloc[next_idx].get("Close"), price) or price
        new_net_worth = self.balance + self.shares_held * next_price

        # ---- Risk-adjusted reward ----
        prev_nw = self.net_worth if self.net_worth > 0 else self.initial_balance
        pnl_pct = (new_net_worth - prev_nw) / prev_nw
        self.ret_window.append(pnl_pct)

        # Rolling Sharpe shaping: rewards smooth equity curves, not lucky spikes.
        sharpe_bonus = 0.0
        if len(self.ret_window) >= 5:
            arr = np.asarray(self.ret_window, dtype=np.float64)
            std = float(arr.std())
            sharpe_bonus = SHARPE_WEIGHT * (float(arr.mean()) / std) if std > 1e-9 else 0.0

        # Drawdown penalty — LINEAR now. Shallow DD costs nothing meaningful;
        # 20% DD costs 0.05 per bar which keeps the agent honest without
        # training it to flee to cash at the first red bar.
        self.peak_net_worth = max(self.peak_net_worth, new_net_worth)
        dd = (self.peak_net_worth - new_net_worth) / max(self.peak_net_worth, 1e-6)
        dd_cost = DD_PENALTY * dd

        # Holding cost only when BOTH exposed AND ATR is high — cheap during
        # calm bull markets, pricier during chop.
        if self.shares_held > 0:
            vol_ratio = atr / max(price, 1e-6)
            holding_cost = HOLDING_PENALTY * vol_ratio
        else:
            holding_cost = 0.0

        # Opportunity cost: tiny penalty for being flat during a clear uptrend.
        # Measured as positive 5-bar momentum; discourages the "always HOLD"
        # degenerate strategy that the previous reward recipe encouraged.
        opp_cost = 0.0
        if self.shares_held <= 0 and self.current_step >= 5 and idx >= 5:
            try:
                past = _safe(self.df.iloc[idx - 5]["Close"], price) or price
                mom = (price - past) / past
                if mom > 0.005:  # 0.5% up over 5 bars
                    opp_cost = OPPORTUNITY_COST * mom
            except Exception:
                pass

        reward = pnl_pct + sharpe_bonus - dd_cost - holding_cost - opp_cost

        self.net_worth = new_net_worth

        info = {
            "net_worth": float(self.net_worth),
            "price": float(next_price),
            "drawdown": float(dd),
            "sharpe_bonus": float(sharpe_bonus),
            "opp_cost": float(opp_cost),
        }
        return self._obs(), float(reward), terminated, False, info
