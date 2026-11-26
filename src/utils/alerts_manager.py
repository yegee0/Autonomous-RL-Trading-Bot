import os
import json
import time
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests


class AlertLevel(Enum):
    INFO = "ℹ️"
    WARNING = "⚠️"
    CRITICAL = "🚨"
    SUCCESS = "✅"
    ERROR = "❌"


class SignalType(Enum):
    HOLD = "HOLD"
    BUY = "BUY"
    STRONG_BUY = "STRONG_BUY"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class Alert:
    ticker: str
    level: AlertLevel
    title: str
    message: str
    timestamp: str
    data: Optional[Dict] = None


@dataclass
class TradingSignal:
    ticker: str
    signal_type: SignalType
    confidence: float
    sentiment: float
    price: float
    rsi: float = 0.0
    macd: float = 0.0
    reason: str = ""


class TelegramAlerter:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.rate_limit_count = 0
        self.rate_limit_time = time.time()
        print(f"✅ Telegram alerter initialized (Chat: {chat_id})")

    def _check_rate_limit(self, max_per_minute: int = 30) -> bool:
        current_time = time.time()
        if current_time - self.rate_limit_time > 60:
            self.rate_limit_count = 0
            self.rate_limit_time = current_time
        if self.rate_limit_count >= max_per_minute:
            print(f"⚠️ Telegram rate limit reached ({max_per_minute}/min)")
            return False
        self.rate_limit_count += 1
        return True

    def send_message(self, text: str, parse_mode: str = "Markdown",
                     reply_markup: dict = None) -> bool:
        if not self._check_rate_limit():
            return False

        try:
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode,
            }

            if reply_markup:
                payload['reply_markup'] = json.dumps(reply_markup)

            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                return True
            else:
                print(f"❌ Telegram error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False

    def send_trading_signal(self, signal: TradingSignal) -> bool:
        signal_emoji = {
            SignalType.HOLD: "⏸️",
            SignalType.BUY: "🟢",
            SignalType.STRONG_BUY: "🚀",
            SignalType.SELL: "🔴",
            SignalType.STRONG_SELL: "📉",
        }

        signal_color = {
            SignalType.HOLD: "🟡",
            SignalType.BUY: "🟢",
            SignalType.STRONG_BUY: "🟢",
            SignalType.SELL: "🔴",
            SignalType.STRONG_SELL: "🔴",
        }

        emoji = signal_emoji.get(signal.signal_type, "⚪")
        color = signal_color.get(signal.signal_type, "⚪")

        sentiment_emoji = "🟢" if signal.sentiment > 0.1 else "🔴" if signal.sentiment < -0.1 else "⚪"

        message = f"""
{emoji} *TRADING SIGNAL - {signal.ticker}*

{color} *Signal:* `{signal.signal_type.value}`
💹 *Price:* `${signal.price:,.2f}`
🎯 *Confidence:* `{signal.confidence * 100:.1f}%`

📊 *Technical Indicators:*
• RSI: `{signal.rsi:.1f}`
• MACD: `{signal.macd:.4f}`
• Sentiment: {sentiment_emoji} `{signal.sentiment:+.2f}`

{f"📝 *Reason:* {signal.reason}" if signal.reason else ""}

⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

        buttons = {
            "inline_keyboard": [[
                {"text": f"📊 Chart {signal.ticker}",
                 "url": f"https://www.tradingview.com/chart/?symbol={signal.ticker}"}
            ]]
        }

        return self.send_message(message, reply_markup=buttons)

    def send_alert(self, alert: Alert) -> bool:
        message = f"""
{alert.level.value} *{alert.title}*

*Ticker:* {alert.ticker}
*Time:* {alert.timestamp}

{alert.message}
"""

        buttons = None
        if alert.ticker:
            buttons = {
                "inline_keyboard": [[
                    {"text": f"📊 {alert.ticker}",
                     "url": f"https://www.tradingview.com/chart/?symbol={alert.ticker}"}
                ]]
            }

        return self.send_message(message, reply_markup=buttons)


class SignalBroadcaster:
    """Broadcasts trading signals to multiple channels"""

    def __init__(self, telegram_token: str = None, telegram_chat: str = None):
        self.telegram = None
        self.last_signal = {}
        self.signal_history = []
        self.min_signal_interval = 60

        if telegram_token and telegram_chat:
            self.telegram = TelegramAlerter(telegram_token, telegram_chat)

    def set_telegram(self, token: str, chat_id: str):
        self.telegram = TelegramAlerter(token, chat_id)

    def _should_send_signal(self, ticker: str, signal_type: SignalType) -> bool:
        key = f"{ticker}_{signal_type.value}"
        last_time = self.last_signal.get(key)

        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self.min_signal_interval:
                return False

        return True

    def broadcast_signal(self, signal: TradingSignal, force: bool = False) -> bool:
        if not force and not self._should_send_signal(signal.ticker, signal.signal_type):
            print(f"⏰ Signal rate limited for {signal.ticker}")
            return False

        success = False

        if self.telegram:
            if self.telegram.send_trading_signal(signal):
                success = True
                print(f"✅ Signal sent to Telegram: {signal.ticker} - {signal.signal_type.value}")

        if success:
            key = f"{signal.ticker}_{signal.signal_type.value}"
            self.last_signal[key] = datetime.now()
            self.signal_history.append({
                'ticker': signal.ticker,
                'signal': signal.signal_type.value,
                'confidence': signal.confidence,
                'price': signal.price,
                'timestamp': datetime.now().isoformat()
            })

        return success

    def broadcast_from_action(self, ticker: str, action: int, confidence: float,
                              sentiment: float, price: float, rsi: float = 50,
                              macd: float = 0, force: bool = False) -> bool:
        """Convert action int to signal and broadcast"""

        action_map = {
            0: SignalType.HOLD,
            1: SignalType.BUY,
            2: SignalType.BUY,
            3: SignalType.STRONG_BUY,
            4: SignalType.SELL,
            5: SignalType.SELL,
            6: SignalType.STRONG_SELL,
        }

        reason_map = {
            0: "Market direction uncertain",
            1: "AI suggests light accumulation (25%)",
            2: "AI suggests accumulation (50%)",
            3: "Strong buy signal - full position",
            4: "AI suggests light reduction (25%)",
            5: "AI suggests reduction (50%)",
            6: "Strong sell signal - exit position",
        }

        signal_type = action_map.get(action, SignalType.HOLD)
        reason = reason_map.get(action, "")

        signal = TradingSignal(
            ticker=ticker,
            signal_type=signal_type,
            confidence=confidence,
            sentiment=sentiment,
            price=price,
            rsi=rsi,
            macd=macd,
            reason=reason
        )

        return self.broadcast_signal(signal, force=force)


class AlertsManager:
    def __init__(self):
        self.telegram: Optional[TelegramAlerter] = None
        self.broadcaster: Optional[SignalBroadcaster] = None
        self.alert_history: List[Alert] = []
        self.last_alerts: Dict[str, datetime] = {}
        self.min_alert_interval = 300

    def add_telegram(self, bot_token: str, chat_id: str):
        self.telegram = TelegramAlerter(bot_token, chat_id)
        self.broadcaster = SignalBroadcaster(bot_token, chat_id)

    def get_broadcaster(self) -> Optional[SignalBroadcaster]:
        return self.broadcaster

    def send_alert(self, alert: Alert, force: bool = False) -> bool:
        if not force:
            alert_key = f"{alert.ticker}_{alert.level.name}"
            last_alert_time = self.last_alerts.get(alert_key)
            if last_alert_time:
                time_since = (datetime.now() - last_alert_time).total_seconds()
                if time_since < self.min_alert_interval:
                    print(f"⏰ Alert rate limited (waited {time_since:.0f}s)")
                    return False

        success = False

        if self.telegram:
            if self.telegram.send_alert(alert):
                success = True

        self.alert_history.append(alert)
        alert_key = f"{alert.ticker}_{alert.level.name}"
        self.last_alerts[alert_key] = datetime.now()

        return success

    def alert_buy_signal(self, ticker: str, confidence: float, reason: str = ""):
        alert = Alert(
            ticker=ticker,
            level=AlertLevel.SUCCESS,
            title=f"BUY Signal - {ticker}",
            message=f"Confidence: {confidence:.1%}\n{reason}",
            timestamp=datetime.now().isoformat(),
            data={'confidence': confidence}
        )
        return self.send_alert(alert)

    def alert_sell_signal(self, ticker: str, confidence: float, reason: str = ""):
        alert = Alert(
            ticker=ticker,
            level=AlertLevel.WARNING,
            title=f"SELL Signal - {ticker}",
            message=f"Confidence: {confidence:.1%}\n{reason}",
            timestamp=datetime.now().isoformat(),
            data={'confidence': confidence}
        )
        return self.send_alert(alert)

    def alert_price_milestone(self, ticker: str, price: float, milestone_type: str = ""):
        alert = Alert(
            ticker=ticker,
            level=AlertLevel.INFO,
            title=f"{milestone_type} - ${price:.2f}",
            message=f"{ticker} reached ${price:.2f}",
            timestamp=datetime.now().isoformat(),
            data={'price': price}
        )
        return self.send_alert(alert)

    def alert_error(self, ticker: str, error_msg: str):
        alert = Alert(
            ticker=ticker,
            level=AlertLevel.ERROR,
            title=f"Error - {ticker}",
            message=error_msg,
            timestamp=datetime.now().isoformat(),
        )
        return self.send_alert(alert)

    def get_summary(self) -> Dict:
        summary = {
            'total_alerts': len(self.alert_history),
            'by_level': {},
            'by_ticker': {},
        }
        for alert in self.alert_history:
            level_name = alert.level.name
            summary['by_level'][level_name] = summary['by_level'].get(level_name, 0) + 1
            summary['by_ticker'][alert.ticker] = summary['by_ticker'].get(alert.ticker, 0) + 1
        return summary


def get_default_broadcaster(chat_id: str) -> Optional[SignalBroadcaster]:
    """Build a broadcaster from the TELEGRAM_BOT_TOKEN env var."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("⚠️ TELEGRAM_BOT_TOKEN not set; broadcaster disabled.")
        return None
    return SignalBroadcaster(token, chat_id)


if __name__ == "__main__":
    print("🧪 Testing Alerts Manager...")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat:
        print("⚠️ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to run this smoke test.")
    else:
        manager = AlertsManager()
        manager.add_telegram(token, chat)
        broadcaster = manager.get_broadcaster()
        if broadcaster:
            signal = TradingSignal(
                ticker="BTC-USD",
                signal_type=SignalType.BUY,
                confidence=0.75,
                sentiment=0.3,
                price=45000.0,
                rsi=35.5,
                macd=150.25,
                reason="RSI oversold, MACD bullish crossover"
            )
            broadcaster.broadcast_signal(signal)

    print("✅ Test complete!")
