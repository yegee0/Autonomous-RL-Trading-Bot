from typing import List, Literal

from pydantic import BaseModel


class BacktestMarker(BaseModel):
    time: int
    kind: Literal["buy", "sell"]
    price: float


class BacktestResponse(BaseModel):
    ticker: str
    source: Literal["ppo", "fallback"]
    initial_balance: float
    final_equity: float
    total_return: float
    buy_hold_return: float
    outperformance: float
    sharpe: float
    volatility: float
    max_drawdown: float
    total_trades: int
    equity_curve: List[float]
    markers: List[BacktestMarker]
    bars: int
