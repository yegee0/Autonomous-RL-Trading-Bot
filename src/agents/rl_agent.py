import os
import numpy as np
import pandas as pd
import streamlit as st
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize, VecFrameStack
from stable_baselines3.common.callbacks import BaseCallback

from src.models.trading_env import StockTradingEnv
from src.models.neural_net import get_ppo_config, get_policy_kwargs
from src.utils.data_loader import fetch_data, fetch_5m_with_indicators
from src.utils.technical_indicators import add_advanced_indicators

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models", "trained")


class StreamlitProgressCallback(BaseCallback):
    def __init__(self, total_timesteps, verbose=0):
        super().__init__(verbose)
        self.total_timesteps = total_timesteps
        self.progress_bar = None
        self.last_update = 0

    def _on_training_start(self) -> None:
        self.progress_bar = st.progress(0, text="🧠 AI Model Training...")

    def _on_step(self) -> bool:
        if self.num_timesteps - self.last_update >= 1000:
            pct = min(1.0, self.num_timesteps / max(1, self.total_timesteps))
            if self.progress_bar:
                self.progress_bar.progress(
                    pct,
                    text=f"📚 Learning... Step: {self.num_timesteps:,}/{self.total_timesteps:,}"
                )
            self.last_update = self.num_timesteps
        return True

    def _on_training_end(self) -> None:
        if self.progress_bar:
            self.progress_bar.progress(1.0, text="✅ Training Complete!")


def make_env(df):
    return lambda: StockTradingEnv(df)


def train_agent(ticker, total_timesteps=100_000, use_streamlit=True):
    try:
        if use_streamlit:
            st.info(f"📥 Preparing {ticker} data...")

        df = fetch_data(ticker, period="60d", interval="5m")
        if df is None or len(df) < 500:
            raise ValueError("Insufficient data. Minimum 500 rows required.")

        df = add_advanced_indicators(df)

        env = DummyVecEnv([make_env(df)])
        env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.0)
        env = VecFrameStack(env, n_stack=10)

        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            policy_kwargs=get_policy_kwargs(),
            **get_ppo_config(),
        )

        callback = StreamlitProgressCallback(total_timesteps) if use_streamlit else None
        model.learn(total_timesteps=total_timesteps, callback=callback)

        os.makedirs(MODELS_DIR, exist_ok=True)
        safe_ticker = ticker.replace("-", "_").replace(".", "_")

        model_path = os.path.join(MODELS_DIR, f"model_{safe_ticker}")
        vecnorm_path = os.path.join(MODELS_DIR, f"model_{safe_ticker}_vecnorm.pkl")

        model.save(model_path)
        env.save(vecnorm_path)

        if use_streamlit:
            st.success(f"✅ Model saved: {model_path}.zip")

        return model_path

    except Exception as e:
        if use_streamlit:
            st.error(f"Training Error: {str(e)}")
        print(f"❌ Error: {e}")
        return None


def load_agent(ticker):
    safe_ticker = ticker.replace("-", "_").replace(".", "_")
    model_path = os.path.join(MODELS_DIR, f"model_{safe_ticker}.zip")
    vecnorm_path = os.path.join(MODELS_DIR, f"model_{safe_ticker}_vecnorm.pkl")

    if not os.path.exists(model_path) or not os.path.exists(vecnorm_path):
        return None, None

    try:
        dummy_df = pd.DataFrame({
            'Close': [100] * 50, 'High': [101] * 50, 'Low': [99] * 50, 'Open': [100] * 50,
            'Volume': [1000] * 50, 'Date': pd.date_range('2024-01-01', periods=50),
            'RSI': [50] * 50, 'MACD': [0] * 50, 'ATR': [1] * 50, 'sentiment': [0] * 50
        })

        env = DummyVecEnv([make_env(dummy_df)])
        env = VecNormalize.load(vecnorm_path, env)
        env.training = False
        env.norm_reward = False
        env = VecFrameStack(env, n_stack=10)

        model = PPO.load(model_path, env=env)
        return model, env

    except Exception as e:
        print(f"Model load error: {e}")
        return None, None


def get_ai_action(ticker, current_price, sentiment_score=0):
    """Get AI prediction with proper confidence calculation"""
    df = fetch_5m_with_indicators(ticker)
    if df.empty:
        return 0, 0.0

    if "sentiment" not in df.columns:
        df["sentiment"] = 0.0
    df.iloc[-1, df.columns.get_loc("sentiment")] = float(sentiment_score)

    model, env = load_agent(ticker)
    if not model:
        return calculate_fallback_signal(df, sentiment_score)

    try:
        n_stack = 10
        tail = df.tail(n_stack).copy()
        if len(tail) < n_stack:
            pad = pd.concat([tail.iloc[[0]]] * (n_stack - len(tail)), ignore_index=True)
            tail = pd.concat([pad, tail], ignore_index=True)

        stacked = []
        for _, row in tail.iterrows():
            obs_i = np.array([
                10000.0,
                0.0,
                float(row.get("Close", current_price)),
                float(row.get("sentiment", sentiment_score)),
                float(row.get("RSI", 50)),
                float(row.get("MACD", 0)),
                float(row.get("ATR", current_price * 0.01)),
            ], dtype=np.float32).reshape(1, -1)
            # VecNormalize is wrapped inside VecFrameStack; normalize per-step raw obs
            vecnorm = env.venv if hasattr(env, "venv") else env
            stacked.append(vecnorm.normalize_obs(obs_i))

        obs_stacked = np.concatenate(stacked, axis=1).astype(np.float32)

        action, _states = model.predict(obs_stacked, deterministic=False)
        action_probs = get_action_probabilities(model, obs_stacked)
        confidence = calculate_confidence(action_probs, int(action[0]))

        return int(action[0]), confidence

    except Exception as e:
        print(f"Prediction error: {e}")
        return calculate_fallback_signal(df, sentiment_score)


def get_action_probabilities(model, obs):
    """Extract action probabilities from PPO model"""
    try:
        import torch
        with torch.no_grad():
            obs_tensor = torch.as_tensor(obs).float()
            distribution = model.policy.get_distribution(obs_tensor)
            probs = distribution.distribution.probs.cpu().numpy()
            return probs[0]
    except Exception:
        return None


def calculate_confidence(action_probs, chosen_action):
    """Calculate confidence based on action probability distribution"""
    if action_probs is None:
        return 0.5

    try:
        chosen_prob = action_probs[chosen_action]
        max_prob = np.max(action_probs)
        entropy = -np.sum(action_probs * np.log(action_probs + 1e-10))
        max_entropy = np.log(len(action_probs))

        normalized_entropy = entropy / max_entropy
        confidence = chosen_prob * (1 - normalized_entropy * 0.5)
        confidence = np.clip(confidence, 0.1, 0.99)

        return float(confidence)
    except Exception:
        return 0.5


def calculate_fallback_signal(df, sentiment_score):
    """Calculate signal when no model is available - improved confidence"""
    try:
        last_row = df.iloc[-1]
        rsi = float(last_row.get("RSI", 50))
        macd = float(last_row.get("MACD", 0))
        macd_signal = float(last_row.get("MACD_SIGNAL", 0))
        atr = float(last_row.get("ATR", 0))
        close = float(last_row.get("Close", 0))

        score = 0
        confidence_sum = 0
        signal_count = 0

        # RSI Analysis (stronger weight)
        if rsi < 20:
            score += 3
            confidence_sum += 0.90
            signal_count += 1
        elif rsi < 30:
            score += 2
            confidence_sum += 0.80
            signal_count += 1
        elif rsi < 40:
            score += 1
            confidence_sum += 0.65
            signal_count += 1
        elif rsi > 80:
            score -= 3
            confidence_sum += 0.90
            signal_count += 1
        elif rsi > 70:
            score -= 2
            confidence_sum += 0.80
            signal_count += 1
        elif rsi > 60:
            score -= 1
            confidence_sum += 0.65
            signal_count += 1
        else:
            confidence_sum += 0.50
            signal_count += 1

        # MACD Analysis
        macd_diff = macd - macd_signal
        if macd_diff > 0:
            score += 1
            strength = min(abs(macd_diff) / (atr + 0.0001), 1.0)
            confidence_sum += 0.60 + (strength * 0.25)
            signal_count += 1
        elif macd_diff < 0:
            score -= 1
            strength = min(abs(macd_diff) / (atr + 0.0001), 1.0)
            confidence_sum += 0.60 + (strength * 0.25)
            signal_count += 1

        # Sentiment Analysis
        if sentiment_score > 0.5:
            score += 2
            confidence_sum += 0.75
            signal_count += 1
        elif sentiment_score > 0.2:
            score += 1
            confidence_sum += 0.65
            signal_count += 1
        elif sentiment_score < -0.5:
            score -= 2
            confidence_sum += 0.75
            signal_count += 1
        elif sentiment_score < -0.2:
            score -= 1
            confidence_sum += 0.65
            signal_count += 1

        # Determine action
        if score >= 4:
            action = 3  # Strong buy
        elif score >= 2:
            action = 2  # Buy
        elif score >= 1:
            action = 1  # Weak buy
        elif score <= -4:
            action = 6  # Strong sell
        elif score <= -2:
            action = 5  # Sell
        elif score <= -1:
            action = 4  # Weak sell
        else:
            action = 0  # Hold

        # Calculate final confidence
        base_confidence = confidence_sum / max(signal_count, 1)

        # Boost confidence for extreme signals
        if abs(score) >= 4:
            base_confidence = min(base_confidence * 1.15, 0.95)
        elif abs(score) >= 2:
            base_confidence = min(base_confidence * 1.05, 0.90)

        confidence = np.clip(base_confidence, 0.35, 0.95)

        return action, float(confidence)

    except Exception as e:
        print(f"Fallback signal error: {e}")
        return 0, 0.50