"""PPO agent loader + inference against the scale-invariant trading env.

Policy priority:
  1. Generalist model (``model_general.zip`` + ``model_general_vecnorm.pkl``).
  2. Per-ticker model (legacy fallback).
  3. Rule-based fallback signal.
"""
from __future__ import annotations

import os
import threading
from typing import Callable, Optional, Tuple

import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv, VecFrameStack, VecNormalize

from src.models.neural_net import get_policy_kwargs, get_ppo_config
from src.models.trading_env import OBS_DIM, StockTradingEnv, build_observation
from src.utils.data_loader import fetch_5m_with_indicators
from src.utils.technical_indicators import add_advanced_indicators

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models", "trained")
N_STACK = 10

_MODEL_CACHE: dict = {}
_LOAD_LOCK = threading.Lock()


class LoggingProgressCallback(BaseCallback):
    def __init__(self, total_timesteps: int, log_every: int = 1000,
                 on_progress: Optional[Callable[[float, int, int], None]] = None, verbose: int = 0):
        super().__init__(verbose)
        self.total_timesteps = total_timesteps
        self.log_every = log_every
        self.on_progress = on_progress
        self.last_update = 0

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_update >= self.log_every:
            pct = min(1.0, self.num_timesteps / max(1, self.total_timesteps))
            if self.on_progress:
                self.on_progress(pct, self.num_timesteps, self.total_timesteps)
            else:
                print(f"[train] {self.num_timesteps:,}/{self.total_timesteps:,} ({pct * 100:.1f}%)")
            self.last_update = self.num_timesteps
        return True


def _dummy_frame(n: int = 60) -> pd.DataFrame:
    """Minimal frame used only to stand up the VecNormalize env for inference."""
    return pd.DataFrame(
        {
            "Close": np.linspace(100, 101, n),
            "High": np.linspace(101, 102, n),
            "Low": np.linspace(99, 100, n),
            "Open": np.linspace(100, 101, n),
            "Volume": np.full(n, 1000.0),
            "RSI": np.full(n, 50.0),
            "MACD": np.zeros(n),
            "MACD_SIGNAL": np.zeros(n),
            "ATR": np.full(n, 1.0),
            "sentiment": np.zeros(n),
        }
    )


def _safe_ticker(ticker: str) -> str:
    return ticker.replace("-", "_").replace(".", "_")


def _paths_for(key: str) -> Tuple[str, str]:
    return (
        os.path.join(MODELS_DIR, f"model_{key}.zip"),
        os.path.join(MODELS_DIR, f"model_{key}_vecnorm.pkl"),
    )


def _load_pair(model_path: str, vecnorm_path: str):
    if not (os.path.exists(model_path) and os.path.exists(vecnorm_path)):
        return None, None
    env = DummyVecEnv([lambda: StockTradingEnv(_dummy_frame())])
    env = VecNormalize.load(vecnorm_path, env)
    env.training = False
    env.norm_reward = False
    env = VecFrameStack(env, n_stack=N_STACK)
    model = PPO.load(model_path, env=env)
    return model, env


def load_agent(ticker: str):
    """Return (model, env). Prefers the generalist, then per-ticker, else (None, None)."""
    key = _safe_ticker(ticker)
    with _LOAD_LOCK:
        if "general" in _MODEL_CACHE:
            return _MODEL_CACHE["general"]
        general_paths = _paths_for("general")
        model, env = _load_pair(*general_paths)
        if model:
            _MODEL_CACHE["general"] = (model, env)
            return model, env

        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        model, env = _load_pair(*_paths_for(key))
        if model:
            _MODEL_CACHE[key] = (model, env)
            return model, env
    return None, None


def _ensure_sentiment(df: pd.DataFrame, sentiment: float) -> pd.DataFrame:
    if "sentiment" not in df.columns:
        df = df.copy()
        df["sentiment"] = 0.0
    df.iloc[-1, df.columns.get_loc("sentiment")] = float(sentiment)
    return df


def _stacked_obs(df: pd.DataFrame, env, initial_balance: float = 10_000.0) -> np.ndarray:
    """Build the FrameStack(n=10) VecNormalize-normalised obs for inference."""
    tail = df.tail(N_STACK).reset_index(drop=True)
    while len(tail) < N_STACK:
        tail = pd.concat([tail.iloc[[0]], tail], ignore_index=True)

    vecnorm = env.venv if hasattr(env, "venv") else env
    frames = []
    for i in range(len(tail)):
        raw = build_observation(tail, i, initial_balance, 0.0, initial_balance).reshape(1, -1)
        frames.append(vecnorm.normalize_obs(raw))
    return np.concatenate(frames, axis=1).astype(np.float32)


def _action_probs(model, obs: np.ndarray):
    try:
        import torch
        device = model.policy.device if hasattr(model.policy, "device") else "cpu"
        with torch.no_grad():
            tensor = torch.as_tensor(obs, device=device).float()
            dist = model.policy.get_distribution(tensor)
            return dist.distribution.probs.cpu().numpy()[0]
    except Exception as e:
        print(f"[infer] action-probs extraction failed: {e}")
        return None


def _confidence(probs, chosen: int) -> float:
    if probs is None:
        return 0.5
    try:
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        max_entropy = np.log(len(probs))
        norm_entropy = entropy / max_entropy
        conf = probs[chosen] * (1 - norm_entropy * 0.5)
        return float(np.clip(conf, 0.1, 0.99))
    except Exception:
        return 0.5


def get_ai_action(ticker: str, current_price: float, sentiment_score: float = 0.0) -> Tuple[int, float]:
    """Return (action, confidence) using the best available PPO model, else fallback."""
    df = fetch_5m_with_indicators(ticker)
    if df is None or df.empty:
        return 0, 0.0
    df = _ensure_sentiment(df, sentiment_score)

    model, env = load_agent(ticker)
    if model is None:
        return calculate_fallback_signal(df, sentiment_score)

    try:
        obs = _stacked_obs(df, env)
        action, _ = model.predict(obs, deterministic=False)
        chosen = int(action[0])
        probs = _action_probs(model, obs)
        return chosen, _confidence(probs, chosen)
    except Exception as e:
        print(f"[infer] PPO failed, using fallback: {e}")
        return calculate_fallback_signal(df, sentiment_score)


def calculate_fallback_signal(df: pd.DataFrame, sentiment_score: float) -> Tuple[int, float]:
    """Deterministic rule-based signal used when no PPO model is available."""
    try:
        last = df.iloc[-1]
        rsi = float(last.get("RSI", 50))
        macd = float(last.get("MACD", 0))
        macd_signal = float(last.get("MACD_SIGNAL", 0))
        atr = float(last.get("ATR", 0))

        score = 0
        conf_sum = 0.0
        count = 0

        # RSI
        if rsi < 20: score += 3; conf_sum += 0.90; count += 1
        elif rsi < 30: score += 2; conf_sum += 0.80; count += 1
        elif rsi < 40: score += 1; conf_sum += 0.65; count += 1
        elif rsi > 80: score -= 3; conf_sum += 0.90; count += 1
        elif rsi > 70: score -= 2; conf_sum += 0.80; count += 1
        elif rsi > 60: score -= 1; conf_sum += 0.65; count += 1
        else: conf_sum += 0.50; count += 1

        # MACD histogram
        diff = macd - macd_signal
        if diff != 0:
            strength = min(abs(diff) / (atr + 1e-4), 1.0)
            if diff > 0: score += 1
            else: score -= 1
            conf_sum += 0.60 + strength * 0.25
            count += 1

        # Sentiment
        if sentiment_score > 0.5: score += 2; conf_sum += 0.75; count += 1
        elif sentiment_score > 0.2: score += 1; conf_sum += 0.65; count += 1
        elif sentiment_score < -0.5: score -= 2; conf_sum += 0.75; count += 1
        elif sentiment_score < -0.2: score -= 1; conf_sum += 0.65; count += 1

        if score >= 4: action = 3
        elif score >= 2: action = 2
        elif score >= 1: action = 1
        elif score <= -4: action = 6
        elif score <= -2: action = 5
        elif score <= -1: action = 4
        else: action = 0

        base_conf = conf_sum / max(count, 1)
        if abs(score) >= 4: base_conf = min(base_conf * 1.15, 0.95)
        elif abs(score) >= 2: base_conf = min(base_conf * 1.05, 0.90)
        return action, float(np.clip(base_conf, 0.35, 0.95))
    except Exception as e:
        print(f"[fallback] error: {e}")
        return 0, 0.5


def make_env_factory(df: pd.DataFrame):
    return lambda: StockTradingEnv(df)


def train_agent(ticker: str, total_timesteps: int = 100_000, on_progress=None):
    """Legacy single-ticker trainer. Prefer ``scripts/train_general.py``."""
    from src.utils.data_loader import fetch_data
    df = fetch_data(ticker, period="60d", interval="5m")
    if df is None or len(df) < 500:
        raise ValueError("Insufficient data. Minimum 500 rows required.")
    df = add_advanced_indicators(df)

    env = DummyVecEnv([make_env_factory(df)])
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)
    env = VecFrameStack(env, n_stack=N_STACK)

    model = PPO("MlpPolicy", env, verbose=1, policy_kwargs=get_policy_kwargs(), **get_ppo_config())
    model.learn(total_timesteps=total_timesteps,
                callback=LoggingProgressCallback(total_timesteps, on_progress=on_progress))

    os.makedirs(MODELS_DIR, exist_ok=True)
    key = _safe_ticker(ticker)
    model_path = os.path.join(MODELS_DIR, f"model_{key}")
    vecnorm_path = os.path.join(MODELS_DIR, f"model_{key}_vecnorm.pkl")
    model.save(model_path)
    env.save(vecnorm_path)
    print(f"[train] Model saved: {model_path}.zip")
    return model_path
