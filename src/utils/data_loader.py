import time
import warnings
from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd
import ta
import yfinance as yf

warnings.filterwarnings('ignore')

_CACHE: dict = {}
_CACHE_TS: dict = {}


def _cached(key: str, ttl: int) -> Optional[pd.DataFrame]:
    hit = _CACHE.get(key)
    if hit is None:
        return None
    if time.time() - _CACHE_TS.get(key, 0) > ttl:
        return None
    return hit


def _set_cache(key: str, df: pd.DataFrame) -> None:
    _CACHE[key] = df
    _CACHE_TS[key] = time.time()


def fetch_data(ticker, period="1y", interval="1d"):
    """Fetch price data - no cache for fresh data"""
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)

        if data is None or data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data.reset_index(inplace=True)

        if 'Datetime' in data.columns:
            data.rename(columns={'Datetime': 'Date'}, inplace=True)

        required_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in data.columns]

        if missing_cols:
            return None

        return data

    except Exception as e:
        print(f"Data fetch error: {e}")
        return None


def fetch_5m_with_indicators(ticker, lookback_days="5d"):
    """Fetch 5m data with indicators - 60s in-memory cache"""
    cache_key = f"5m:{ticker}:{lookback_days}"
    cached = _cached(cache_key, ttl=60)
    if cached is not None:
        return cached

    try:
        df = yf.download(ticker, period=lookback_days, interval="5m", progress=False)

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        if 'Datetime' in df.columns:
            df.rename(columns={'Datetime': 'Date'}, inplace=True)

        df["RSI"] = ta.momentum.rsi(df["Close"], window=14)

        macd = ta.trend.MACD(close=df["Close"])
        df["MACD"] = macd.macd()
        df["MACD_SIGNAL"] = macd.macd_signal()

        df["ATR"] = ta.volatility.average_true_range(df["High"], df["Low"], df["Close"], window=14)

        df = df.dropna()
        _set_cache(cache_key, df)

        return df

    except Exception as e:
        print(f"5m data error: {e}")
        return pd.DataFrame()


def validate_dataframe(df, required_cols=None):
    if df is None or df.empty:
        return False

    if required_cols is None:
        required_cols = ['Close', 'High', 'Low', 'RSI', 'MACD', 'ATR']

    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        return False

    nan_count = df[required_cols].isna().sum().sum()
    if nan_count > 0:
        df = df.dropna()

    for col in required_cols:
        if np.isinf(df[col]).any():
            df[col] = df[col].replace([np.inf, -np.inf], np.nan)
            df = df.dropna()

    return True


def prepare_for_training(df, test_split=0.2):
    if not validate_dataframe(df):
        return None, None

    split_idx = int(len(df) * (1 - test_split))
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()

    return train_df, test_df