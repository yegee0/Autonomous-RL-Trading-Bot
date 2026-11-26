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
from typing import Dict, List, Optional

import pandas as pd

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack, VecNormalize

from src.agents.rl_agent import LoggingProgressCallback, MODELS_DIR, N_STACK
from src.models.crisis_env import CrisisWrapperEnv
from src.models.neural_net import get_policy_kwargs, get_ppo_config
from src.utils.data_loader import fetch_data
from src.utils.regime_filter import filter_frames
from src.utils.technical_indicators import add_advanced_indicators


# Historical crisis windows worth oversampling. Each is a (start, end, label)
# — yfinance gets the bars via explicit start/end so we don't depend on
# "lookback X days from today".
CRISIS_WINDOWS = [
    ("2020-02-15", "2020-04-30", "covid-crash"),
    ("2021-05-01", "2021-07-31", "crypto-may21"),
    ("2022-05-01", "2022-07-31", "luna-collapse"),
    ("2022-11-01", "2022-12-31", "ftx-collapse"),
    ("2024-08-01", "2024-08-15", "yen-carry-unwind"),
]


def _fetch_window(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """yfinance bar pull for an explicit date window (used for crisis periods)."""
    import yfinance as yf  # noqa: WPS433
    try:
        df = yf.download(ticker, start=start, end=end, interval="1d", progress=False)
    except Exception as e:
        print(f"[crisis]   {ticker} {start}→{end} fetch error: {e}")
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    if "Datetime" in df.columns:
        df.rename(columns={"Datetime": "Date"}, inplace=True)
    return df


def load_basket(
    tickers: List[str],
    period: str,
    interval: str,
    min_rows: int = 300,
    include_crisis: bool = True,
) -> Dict[str, pd.DataFrame]:
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

    # Crisis-period frames go into the basket with crisis:* keys so the random
    # picker can land on them, making the policy see these regimes often.
    if include_crisis:
        for t in tickers:
            for start, end, label in CRISIS_WINDOWS:
                df = _fetch_window(t, start, end)
                if df is None or len(df) < 30:
                    continue
                df = add_advanced_indicators(df)
                if len(df) < 30:
                    continue
                if "sentiment" not in df.columns:
                    df["sentiment"] = 0.0
                key = f"crisis:{label}:{t}"
                out[key] = df.reset_index(drop=True)
                print(f"[crisis] {key}: {len(df)} rows ready")
    return out


class MultiTickerEnv(CrisisWrapperEnv):
    """Base trading env that:
      * swaps to a random frame (ticker or crisis period) on each reset
      * injects stochastic flash crashes via CrisisWrapperEnv
      * weights crisis frames higher so the policy sees them often
    """

    def __init__(self, frames: Dict[str, pd.DataFrame], crisis_boost: float = 3.0):
        if not frames:
            raise ValueError("No training frames available")
        self._frames = frames
        self._keys = list(frames.keys())
        weights = [crisis_boost if k.startswith("crisis:") else 1.0 for k in self._keys]
        total = sum(weights)
        self._weights = [w / total for w in weights]
        first = frames[self._keys[0]]
        super().__init__(first)

    def reset(self, seed=None, options=None):
        key = random.choices(self._keys, weights=self._weights, k=1)[0]
        self.swap_frame(self._frames[key])
        return super().reset(seed=seed, options=options)


def train(args) -> str:
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    frames = load_basket(
        tickers, args.period, args.interval,
        include_crisis=not getattr(args, "no_crisis", False),
    )
    if not frames:
        raise SystemExit("No usable tickers after download; cannot train.")

    regime = getattr(args, "regime", "all") or "all"
    if regime != "all":
        print(f"[train] filtering frames to regime='{regime}'")
        frames = filter_frames(frames, regime)
        if not frames:
            raise SystemExit(
                f"No frames left after regime filter '{regime}'. "
                f"Try --period longer, --regime all, or relax REGIME_* env vars."
            )

    print(f"[train] basket = {len(frames)} segments; sample keys:")
    for k in list(frames.keys())[:5]:
        print(f"  {k}: {len(frames[k])} rows")

    def make_env():
        return MultiTickerEnv(frames)

    env = DummyVecEnv([make_env])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)
    env = VecFrameStack(env, n_stack=N_STACK)

    # Regime-aware PPO config (ent_coef, gamma differ per head).
    ppo_kwargs = get_ppo_config(regime if regime != "all" else None)

    # On CPU force device='cpu' so SB3 doesn't warn + skips torch GPU probe.
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        policy_kwargs=get_policy_kwargs(),
        device="cpu",
        **ppo_kwargs,
    )

    model.learn(
        total_timesteps=args.timesteps,
        callback=LoggingProgressCallback(args.timesteps),
    )

    os.makedirs(MODELS_DIR, exist_ok=True)
    name = args.name or regime or "general"
    model_path = os.path.join(MODELS_DIR, f"model_{name}")
    vecnorm_path = os.path.join(MODELS_DIR, f"model_{name}_vecnorm.pkl")
    model.save(model_path)
    env.save(vecnorm_path)
    print(f"[train] saved: {model_path}.zip + {vecnorm_path}")
    return model_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", default="BTC-USD,ETH-USD,SOL-USD,AAPL,TSLA,MSFT,NVDA,GOOGL")
    p.add_argument("--period", default="60d")
    p.add_argument("--interval", default="5m")
    p.add_argument("--timesteps", type=int, default=500_000)
    p.add_argument("--no-crisis", action="store_true", help="Disable crisis-period oversampling")
    p.add_argument(
        "--regime",
        default="all",
        choices=["all", "trend", "range", "crisis"],
        help="Train on a filtered regime slice. 'all' uses the whole basket.",
    )
    p.add_argument(
        "--name",
        default=None,
        help='Model filename (defaults to the --regime value). '
             'Ensemble loader picks the one matching the current regime.',
    )
    args = p.parse_args()
    train(args)


if __name__ == "__main__":
    main()
