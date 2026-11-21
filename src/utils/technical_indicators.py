import numpy as np
import ta


def add_advanced_indicators(df):
    try:
        # ============ BOLLINGER BANDS ============
        bb = ta.volatility.BollingerBands(
            close=df["Close"],
            window=20,
            window_dev=2
        )
        df['SMA20'] = bb.bollinger_mavg()
        df['BB_Upper'] = bb.bollinger_hband()
        df['BB_Lower'] = bb.bollinger_lband()
        df['BB_Width'] = df['BB_Upper'] - df['BB_Lower']
        df['BB_Position'] = (df['Close'] - df['BB_Lower']) / df['BB_Width']

        # ============ MOVİNG AVERAGES ============
        df['SMA50'] = ta.trend.sma_indicator(df["Close"], window=50)
        df['SMA200'] = ta.trend.sma_indicator(df["Close"], window=200)
        df['EMA12'] = ta.trend.ema_indicator(df["Close"], window=12)
        df['EMA26'] = ta.trend.ema_indicator(df["Close"], window=26)

        # ============ RSI ============
        df['RSI'] = ta.momentum.rsi(df["Close"], window=14)
        df['RSI_SMA'] = ta.trend.sma_indicator(df['RSI'], window=7)

        # ============ MACD ============
        macd = ta.trend.MACD(close=df["Close"])
        df['MACD'] = macd.macd()
        df['MACD_SIGNAL'] = macd.macd_signal()
        df['MACD_HIST'] = macd.macd_diff()

        # ============ STOCHASTIC ============
        stoch = ta.momentum.StochasticOscillator(
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            window=14,
            smooth_window=3
        )
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()

        # ============ ATR ============
        df['ATR'] = ta.volatility.average_true_range(
            df["High"],
            df["Low"],
            df["Close"],
            window=14
        )

        # ============ VOLUME İNDİKATÖRLERİ ============
        if 'Volume' in df.columns:
            df['Volume_SMA'] = ta.trend.sma_indicator(df["Volume"], window=20)
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']

            # On-Balance Volume
            df['OBV'] = ta.volume.on_balance_volume(df["Close"], df["Volume"])

        # ============ VOLATILITY ============
        returns = df['Close'].pct_change()
        df['Volatility'] = returns.rolling(window=20).std() * np.sqrt(252)

        # ============ PRICE ACTION ============
        df['High_Low_Ratio'] = (df['High'] - df['Low']) / df['Close']
        df['Close_Open_Ratio'] = (df['Close'] - df['Open']) / df['Open']

        # ============ NAN KONTROL ============
        nan_before = df.isna().sum().sum()
        df = df.dropna()
        df.isna().sum().sum()

        if nan_before > 0:
            print(f"⚠️ {nan_before} NaN değer kaldırıldı")

        print(f"✅ {len(df.columns)} indikatör eklendi")

        return df

    except Exception as e:
        print(f"❌ İndikatör ekleme hatası: {e}")
        return df
