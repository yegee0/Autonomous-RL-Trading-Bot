from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Candle(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class Indicators(BaseModel):
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    atr: Optional[float] = None
    sma20: Optional[float] = None
    sma50: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None


class SignalResponse(BaseModel):
    ticker: str
    action: int = Field(..., ge=0, le=6, description="0 hold, 1-3 buy %25/50/100, 4-6 sell %25/50/100")
    action_label: Literal["HOLD", "BUY_25", "BUY_50", "BUY_100", "SELL_25", "SELL_50", "SELL_100"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    direction: Literal["long", "short", "flat"]
    source: Literal["ppo", "fallback"]
    sentiment: float = 0.0
    price: float


class RiskMetrics(BaseModel):
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    var_95: float = 0.0


class PositionSizing(BaseModel):
    position_size_usd: float = 0.0
    position_size_pct: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    kelly_fraction: float = 0.0


class NewsItem(BaseModel):
    title: str
    source: str
    link: str
    sentiment: float
    time_ago: Optional[str] = None


class AnalyzeRequest(BaseModel):
    ticker: str
    period: str = "3mo"
    interval: str = "1d"


class AnalyzeResponse(BaseModel):
    ticker: str
    price: float
    candles: List[Candle]
    indicators: Indicators
    signal: SignalResponse
    risk: RiskMetrics
    sizing: PositionSizing
    news: List[NewsItem] = []
    sentiment_score: float = 0.0


class TickerMeta(BaseModel):
    symbol: str
    name: str
    asset_class: Literal["crypto", "stock", "bist"]
    model_available: bool
