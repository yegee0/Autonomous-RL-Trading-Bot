"""Train a single generalist PPO policy over a basket of tickers.

Usage:
    python scripts/train_general.py \
        --tickers BTC-USD,ETH-USD,AAPL,TSLA,MSFT,NVDA \
        --timesteps 300000 \
        --period 60d --interval 5m

Each env sample draws a random ticker frame on every reset so the policy
never over-fits to a single asset. Observations are already scale-invariant
(see ``src/models/trading_env.py``) so BTC at $60k and AAPL at $200 share
the same policy space.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack, VecNormalize

from src.agents.rl_agent import LoggingProgressCallback, MODELS_DIR, N_STACK
from src.models.neural_net import get_policy_kwargs, get_ppo_config
from src.models.trading_env import StockTradingEnv
from src.utils.data_loader import fetch_data
from src.utils.technical_indicators import add_advanced_indicators


def load_basket(tickers: List[str], period: str, interval: str, min_rows: int = 300) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for t in tickers:
        print(f"[data] fetching {t} ({period}, {interval})")
        df = fetch_data(t, period=period, interval=interval)
        if df is None or len(df) < min_rows:
            print(f"[data]   skip {t} — only {0 if df is None else len(df)} rows")
            continue
        df = add_advanced_indicators(df)
        if len(df) < min_rows:
            print(f"[data]   skip {t} post-indicators — only {len(df)} rows")
            continue
        if "sentiment" not in df.columns:
            df["sentiment"] = 0.0
        out[t] = df.reset_index(drop=True)
        print(f"[data]   {t}: {len(df)} rows ready")
    return out


class MultiTickerEnv(StockTradingEnv):
    """StockTradingEnv that swaps to a random ticker on each reset."""

    def __init__(self, frames: Dict[str, pd.DataFrame]):
        if not frames:
            raise ValueError("No training frames available")
        self._frames = frames
        self._keys = list(frames.keys())
        first = frames[self._keys[0]]
        super().__init__(first)

    def reset(self, seed=None, options=None):
        key = random.choice(self._keys)
        self.swap_frame(self._frames[key])
        return super().reset(seed=seed, options=options)


def train(args) -> str:
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    frames = load_basket(tickers, args.period, args.interval)
    if not frames:
        raise SystemExit("No usable tickers after download; cannot train.")

    print(f"[train] basket = {list(frames.keys())}")

    def make_env():
        return MultiTickerEnv(frames)

    env = DummyVecEnv([make_env])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)
    env = VecFrameStack(env, n_stack=N_STACK)

    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        policy_kwargs=get_policy_kwargs(),
        **get_ppo_config(),
    )

    model.learn(
        total_timesteps=args.timesteps,
        callback=LoggingProgressCallback(args.timesteps),
    )

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "model_general")
    vecnorm_path = os.path.join(MODELS_DIR, "model_general_vecnorm.pkl")
    model.save(model_path)
    env.save(vecnorm_path)
    print(f"[train] saved: {model_path}.zip + {vecnorm_path}")
    return model_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", default="BTC-USD,ETH-USD,AAPL,TSLA,MSFT,NVDA")
    p.add_argument("--period", default="60d")
    p.add_argument("--interval", default="5m")
    p.add_argument("--timesteps", type=int, default=300_000)
    args = p.parse_args()
    train(args)


if __name__ == "__main__":
    main()
