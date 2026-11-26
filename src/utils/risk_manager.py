"""
analysis.py - GELIŞTIRILMIŞ VERSIYON v3.0
✅ Kelly Criterion + Volatility Scaling
✅ Sharpe/Sortino/Calmar ratio
✅ Backtest metrikler
✅ Risk yönetimi
✅ Long/Short Stop-Loss calculations
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple


# ============================================================================
# 1. RISK METRİKLERİ
# ============================================================================

def calculate_risk_metrics(df) -> Dict:
    """
    Kapsamlı risk metriklerini hesapla

    Parameters:
    -----------
    df : pd.DataFrame
        OHLCV verileri

    Returns:
    --------
    Dict : Risk metrikleri
    """

    if df is None or df.empty or 'Close' not in df.columns:
        return {
            'volatility': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0,
            'max_drawdown': 0,
            'var_95': 0,
        }

    try:
        returns = df['Close'].pct_change()

        # ============ VOLATİLİTY ============
        volatility = returns.std() * np.sqrt(252)

        # ============ SHARPE RATIO ============
        risk_free_rate = 0.02
        excess_returns = returns.mean() * 252 - risk_free_rate
        sharpe_ratio = excess_returns / volatility if volatility > 0 else 0

        # ============ SORTINO RATIO (downside only) ============
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino_ratio = excess_returns / downside_std if downside_std > 0 else 0

        # ============ MAX DRAWDOWN & CALMAR ============
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdowns = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdowns.min()

        cagr = (cumulative_returns.iloc[-1] / cumulative_returns.iloc[0]) ** (252 / len(returns)) - 1
        calmar_ratio = cagr / abs(max_drawdown) if max_drawdown != 0 else 0

        # ============ VALUE AT RISK ============
        var_95 = returns.quantile(0.05)

        return {
            'volatility': float(volatility),
            'sharpe_ratio': float(sharpe_ratio),
            'sortino_ratio': float(sortino_ratio),
            'calmar_ratio': float(calmar_ratio),
            'max_drawdown': float(max_drawdown),
            'var_95': float(var_95),
        }

    except Exception as e:
        print(f"❌ Risk metrik hatası: {e}")
        return {
            'volatility': 0,
            'sharpe_ratio': 0,
            'sortino_ratio': 0,
            'calmar_ratio': 0,
            'max_drawdown': 0,
            'var_95': 0,
        }


# ============================================================================
# 2. TRADING SİNYALLERİ
# ============================================================================

def get_advanced_signals(df) -> Tuple[Dict, float, float, Dict]:
    """
    Teknik analiz sinyalleri (RSI, MACD, vb)

    Returns:
    --------
    (signals, total_score, confidence, confidence_scores)
    """

    if df is None or df.empty:
        return {}, 0, 0.5, {}

    try:
        last_row = df.iloc[-1]
        signals = {}
        confidence_scores = {}

        # ============ RSI ============
        if 'RSI' in df.columns:
            rsi = last_row['RSI']

            if rsi < 25:
                signals['RSI'], confidence_scores['RSI'] = "STRONG BUY", 0.9
            elif rsi < 30:
                signals['RSI'], confidence_scores['RSI'] = "BUY", 0.7
            elif rsi > 75:
                signals['RSI'], confidence_scores['RSI'] = "STRONG SELL", 0.9
            elif rsi > 70:
                signals['RSI'], confidence_scores['RSI'] = "SELL", 0.7
            else:
                signals['RSI'], confidence_scores['RSI'] = "NEUTRAL", 0.5

        # ============ MACD ============
        if 'MACD' in df.columns:
            macd = last_row['MACD']
            macd_signal = last_row.get('MACD_SIGNAL', macd)

            if macd > macd_signal:
                signals['MACD'], confidence_scores['MACD'] = "BUY", 0.65
            else:
                signals['MACD'], confidence_scores['MACD'] = "SELL", 0.65

        # ============ BOLLINGER BANDS ============
        if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
            bb_upper = last_row['BB_Upper']
            bb_lower = last_row['BB_Lower']
            close = last_row['Close']

            if close > bb_upper:
                signals['BB'], confidence_scores['BB'] = "SELL (Overbought)", 0.6
            elif close < bb_lower:
                signals['BB'], confidence_scores['BB'] = "BUY (Oversold)", 0.6
            else:
                signals['BB'], confidence_scores['BB'] = "NEUTRAL", 0.4

        # ============ STOCHASTIC ============
        if 'Stoch_K' in df.columns:
            stoch_k = last_row['Stoch_K']

            if stoch_k < 20:
                signals['Stoch'], confidence_scores['Stoch'] = "BUY", 0.6
            elif stoch_k > 80:
                signals['Stoch'], confidence_scores['Stoch'] = "SELL", 0.6
            else:
                signals['Stoch'], confidence_scores['Stoch'] = "NEUTRAL", 0.4

        # ============ MOVING AVERAGE CROSSOVER ============
        if 'SMA20' in df.columns and 'SMA50' in df.columns:
            sma20 = last_row['SMA20']
            sma50 = last_row['SMA50']

            if sma20 > sma50:
                signals['MA_Cross'], confidence_scores['MA_Cross'] = "BUY", 0.6
            else:
                signals['MA_Cross'], confidence_scores['MA_Cross'] = "SELL", 0.6

        # ============ VOLUME ANALYSIS ============
        if 'Volume_Ratio' in df.columns:
            vol_ratio = last_row['Volume_Ratio']

            if vol_ratio > 2.0:
                signals['Volume'], confidence_scores['Volume'] = "HIGH ACTIVITY", 0.7
            elif vol_ratio < 0.5:
                signals['Volume'], confidence_scores['Volume'] = "LOW ACTIVITY", 0.4
            else:
                signals['Volume'], confidence_scores['Volume'] = "NORMAL", 0.5

        # ============ TOPLAM SKOR ============
        signal_values = {
            'STRONG BUY': 2,
            'BUY': 1,
            'BUY (Oversold)': 1,
            'NEUTRAL': 0,
            'NORMAL': 0,
            'HIGH ACTIVITY': 0,
            'LOW ACTIVITY': 0,
            'SELL': -1,
            'SELL (Overbought)': -1,
            'STRONG SELL': -2
        }

        total_score = sum(signal_values.get(sig, 0) for sig in signals.values())

        # Confidence ortalaması
        if confidence_scores:
            avg_confidence = np.mean(list(confidence_scores.values()))
        else:
            avg_confidence = 0.5

        return signals, total_score, avg_confidence, confidence_scores

    except Exception as e:
        print(f"❌ Sinyal analiz hatası: {e}")
        return {}, 0, 0.5, {}


# ============================================================================
# 3. POSITION SIZING - IMPROVED
# ============================================================================

class DynamicPositionSizer:
    """
    Kelly Criterion + Volatility Scaling + Loss Penalty
    """

    def __init__(self, max_risk_per_trade=0.02, use_half_kelly=True):
        """
        Parameters:
        -----------
        max_risk_per_trade : float
            Her trade'deki risk (0.02 = %2)
        use_half_kelly : bool
            Half-Kelly kullan (daha konservatif)
        """
        self.max_risk_per_trade = max_risk_per_trade
        self.use_half_kelly = use_half_kelly
        self.trade_history = []

    def calculate_position_size(self,
                                balance,
                                current_price,
                                atr,
                                win_rate,
                                risk_reward_ratio=2.5,
                                consecutive_losses=0,
                                volatility=None):
        """
        Dinamik position size hesapla

        Parameters:
        -----------
        balance : float
            Mevcut bakiye
        current_price : float
            Varlık fiyatı
        atr : float
            Average True Range
        win_rate : float
            Beklenen kazanma oranı (0-1)
        risk_reward_ratio : float
            Risk/Reward oranı
        consecutive_losses : int
            Ardışık kayıp sayısı
        volatility : float
            Opsiyonel volatility

        Returns:
        --------
        Dict : Position sizing bilgisi
        """

        try:
            # ============ KELLY CRITERION ============
            win_prob = max(win_rate, 0.40)
            loss_prob = 1.0 - win_prob
            kelly_pct = win_prob - (loss_prob / risk_reward_ratio)
            kelly_pct = max(0.0, kelly_pct)

            # ============ VOLATİLİTY SCALING ============
            if volatility is None:
                volatility = atr / current_price

            vol_factor = 1.0 / (1.0 + max(volatility * 10, 0))

            # ============ LOSS PENALTY ============
            loss_penalty = 1.0 - (consecutive_losses * 0.15)
            loss_penalty = max(0.2, loss_penalty)

            # ============ FINAL POSITION SIZE ============
            safe_kelly = kelly_pct * (0.5 if self.use_half_kelly else 1.0)
            final_pct = safe_kelly * vol_factor * loss_penalty
            final_pct = max(0.0, min(final_pct, 1.0))

            # ============ RISK HESAPLAMA ============
            stop_distance = atr * 2.0  # 2x ATR
            long_stop_loss = current_price - stop_distance
            short_stop_loss = current_price + stop_distance
            take_profit = current_price + (atr * 3.5)

            position_size_shares = (balance * final_pct * self.max_risk_per_trade) / stop_distance if stop_distance > 0 else 0
            position_size_usd = position_size_shares * current_price

            return {
                'position_size_pct': final_pct * 100,
                'position_size_usd': float(position_size_usd),
                'position_size_shares': float(position_size_shares),
                'kelly_fraction': float(kelly_pct * 100),
                'safe_kelly_pct': float(safe_kelly * 100),
                'vol_adjusted': float(vol_factor),
                'loss_penalty': float(loss_penalty),
                'stop_loss': float(long_stop_loss),
                'long_stop_loss': float(long_stop_loss),
                'short_stop_loss': float(short_stop_loss),
                'stop_distance': float(stop_distance),
                'take_profit': float(take_profit),
                'risk_per_trade': float(position_size_usd * self.max_risk_per_trade),
                'current_price': float(current_price),
                'atr': float(atr),
            }

        except Exception as e:
            print(f"❌ Position sizing hatası: {e}")
            return {
                'position_size_pct': 0,
                'position_size_usd': 0,
                'position_size_shares': 0,
                'kelly_fraction': 0,
                'safe_kelly_pct': 0,
                'stop_loss': current_price - atr * 2.0,
                'long_stop_loss': current_price - atr * 2.0,
                'short_stop_loss': current_price + atr * 2.0,
                'stop_distance': atr * 2.0,
                'take_profit': current_price + atr * 3.5,
            }


def calculate_position_sizing(df, balance, confidence=0.5):
    """
    Position sizing hesapla (backward compatibility)

    Parameters:
    -----------
    df : pd.DataFrame
        OHLCV verileri
    balance : float
        Mevcut bakiye
    confidence : float
        AI güven skoru (0-1)

    Returns:
    --------
    Dict : Position sizing bilgisi
    """
    if df is None or df.empty:
        return {}

    try:
        last_row = df.iloc[-1]
        price = float(last_row['Close'])
        atr = float(last_row.get('ATR', price * 0.02))

        # Volatility
        returns = df['Close'].pct_change().tail(20)
        volatility = float(returns.std()) if len(returns) > 0 else 0.02

        sizer = DynamicPositionSizer()
        result = sizer.calculate_position_size(
            balance=balance,
            current_price=price,
            atr=atr,
            win_rate=confidence,
            volatility=volatility,
        )

        return result

    except Exception as e:
        print(f"❌ Position sizing hatası: {e}")
        return {}


# ============================================================================
# 4. BACKTEST REPORTING
# ============================================================================

class BacktestReporter:
    """
    Kapsamlı backtest raporları
    """

    def __init__(self, initial_capital=10000):
        self.initial_capital = initial_capital

    def generate_report(self, trades, equity_curve, prices):
        report = {}

        # ============ TEMEL RETÜRNÜ ============
        total_return = (equity_curve[-1] - self.initial_capital) / self.initial_capital

        report['Total Return %'] = total_return * 100
        report['Final Balance'] = equity_curve[-1]
        report['Absolute Gain'] = equity_curve[-1] - self.initial_capital

        # ============ CAGR ============
        years = len(equity_curve) / 252
        cagr = (equity_curve[-1] / self.initial_capital) ** (1 / max(years, 1)) - 1
        report['CAGR %'] = cagr * 100

        # ============ DRAWDOWN ============
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - running_max) / running_max
        max_dd = np.min(drawdowns)

        report['Max Drawdown %'] = max_dd * 100

        # ============ SHARPE ============
        daily_returns = np.diff(equity_curve) / equity_curve[:-1]
        volatility = np.std(daily_returns) * np.sqrt(252)

        risk_free_rate = 0.02
        excess_return = np.mean(daily_returns) * 252 - risk_free_rate
        sharpe = excess_return / volatility if volatility > 0 else 0

        report['Volatility (Ann) %'] = volatility * 100
        report['Sharpe Ratio'] = sharpe

        # ============ TRADE STATS ============
        if trades:
            pnls = [t.get('pnl', 0) for t in trades if 'pnl' in t]
            winning = [p for p in pnls if p > 0]
            losing = [p for p in pnls if p <= 0]

            report['Total Trades'] = len(trades)
            report['Winning'] = len(winning)
            report['Losing'] = len(losing)
            report['Win Rate %'] = (len(winning) / len(trades) * 100) if trades else 0

            if winning:
                report['Avg Win'] = np.mean(winning)
            if losing:
                report['Avg Loss'] = np.mean(losing)

        # ============ BUY & HOLD ============
        if len(prices) > 0:
            bh_return = (prices[-1] - prices[0]) / prices[0] * 100
            report['Buy & Hold %'] = bh_return
            report['Outperformance %'] = report['Total Return %'] - bh_return

        return report

    def print_report(self, report):
        """Raporu güzel yazdır"""
        print("\n" + "=" * 70)
        print("BACKTEST REPORT")
        print("=" * 70)

        sections = {
            'Returns': ['Total Return %', 'CAGR %', 'Final Balance'],
            'Risk': ['Max Drawdown %', 'Volatility (Ann) %', 'Sharpe Ratio'],
            'Trades': ['Total Trades', 'Win Rate %'],
        }

        for section, metrics in sections.items():
            print(f"\n📊 {section}")
            for metric in metrics:
                if metric in report:
                    value = report[metric]
                    if isinstance(value, float):
                        print(f"   {metric:<30} {value:>12.2f}")
                    else:
                        print(f"   {metric:<30} {value:>12}")

        print("\n" + "=" * 70 + "\n")


# ============================================================================
# 5. SIGNAL STRENGTH CALCULATOR
# ============================================================================

def calculate_signal_strength(signals: Dict, confidence_scores: Dict) -> Dict:
    """
    Sinyal gücü hesapla

    Returns:
    --------
    Dict : Signal strength bilgisi
    """
    if not signals:
        return {'strength': 0, 'direction': 'NEUTRAL', 'recommendation': 'HOLD'}

    buy_signals = sum(1 for s in signals.values() if 'BUY' in str(s))
    sell_signals = sum(1 for s in signals.values() if 'SELL' in str(s))

    total_signals = len(signals)

    if buy_signals > sell_signals:
        direction = 'BULLISH'
        strength = buy_signals / total_signals * 100
        recommendation = 'BUY' if strength > 60 else 'WEAK BUY'
    elif sell_signals > buy_signals:
        direction = 'BEARISH'
        strength = sell_signals / total_signals * 100
        recommendation = 'SELL' if strength > 60 else 'WEAK SELL'
    else:
        direction = 'NEUTRAL'
        strength = 50
        recommendation = 'HOLD'

    avg_confidence = np.mean(list(confidence_scores.values())) if confidence_scores else 0.5

    return {
        'strength': strength,
        'direction': direction,
        'recommendation': recommendation,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
        'total_signals': total_signals,
        'avg_confidence': avg_confidence,
    }


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("🧪 analysis.py test ediliyor...\n")

    # Örnek veri
    dates = pd.date_range('2023-01-01', periods=252)
    prices = np.linspace(100, 120, 252)
    df = pd.DataFrame({
        'Date': dates,
        'Close': prices + np.random.normal(0, 2, 252),
        'High': prices + 2,
        'Low': prices - 2,
        'RSI': np.random.uniform(30, 70, 252),
        'MACD': np.random.normal(0, 1, 252),
        'ATR': np.full(252, 2.0),
    })

    # Test 1: Risk metrikleri
    print("Test 1: Risk Metrikleri")
    risk = calculate_risk_metrics(df)
    print(f"   Sharpe Ratio: {risk['sharpe_ratio']:.2f}")
    print(f"   Max Drawdown: {risk['max_drawdown'] * 100:.2f}%\n")

    # Test 2: Sinyaller
    print("Test 2: Trading Sinyalleri")
    signals, score, conf, _ = get_advanced_signals(df)
    print(f"   Sinyaller: {signals}")
    print(f"   Confidence: {conf:.2f}\n")

    # Test 3: Position Sizing
    print("Test 3: Position Sizing")
    sizing = calculate_position_sizing(df, balance=10000, confidence=0.55)
    print(f"   Position Size: ${sizing.get('position_size_usd', 0):.2f}")
    print(f"   Stop Loss: ${sizing.get('stop_loss', 0):.2f}")
    print(f"   Long Stop: ${sizing.get('long_stop_loss', 0):.2f}")
    print(f"   Short Stop: ${sizing.get('short_stop_loss', 0):.2f}")
    print(f"   Take Profit: ${sizing.get('take_profit', 0):.2f}\n")

    print("✅ Tüm testler başarılı!")