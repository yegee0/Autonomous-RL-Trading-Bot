"""Thin REST wrapper around the Binance testnet broker.

Every POST goes through the same guardrails stack the paper trades use,
then forwards to live_broker.place_order. Alerts fire on both approval
and rejection.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services import guardrails as gr
from backend.app.services import live_broker as lb
from backend.app.services import market_service as ms
from backend.app.services import paper_store as ps
from src.utils import notifier as notify

router = APIRouter()


class BalanceOut(BaseModel):
    asset: str
    free: float
    locked: float


class LiveStatus(BaseModel):
    enabled: bool
    testnet_host: str
    balances: List[BalanceOut] = []


class LiveOrderRequest(BaseModel):
    ticker: str
    side: str = Field(..., description="buy or sell")
    qty: float = Field(..., gt=0)
    order_type: str = Field(default="MARKET")
    price: Optional[float] = None


class LiveOrderOut(BaseModel):
    order_id: int
    symbol: str
    side: str
    type: str
    status: str
    price: float
    qty: float
    executed_qty: float
    cummulative_quote_qty: float


@router.get("/live/status", response_model=LiveStatus)
def status() -> LiveStatus:
    if not lb.is_enabled():
        return LiveStatus(enabled=False, testnet_host=lb.TESTNET_HOST)
    try:
        balances = [BalanceOut(**b.__dict__) for b in lb.account_balances()]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Binance testnet unreachable: {e}")
    return LiveStatus(enabled=True, testnet_host=lb.TESTNET_HOST, balances=balances)


@router.post("/live/order", response_model=LiveOrderOut)
def place(req: LiveOrderRequest) -> LiveOrderOut:
    if not lb.is_enabled():
        raise HTTPException(
            status_code=403,
            detail="Binance testnet broker is not configured — set BINANCE_TESTNET=1 and keys.",
        )
    ticker = req.ticker.upper().strip()

    # Build a best-effort equity view off the paper ledger so the guardrails
    # still have a reference portfolio size; live-vs-paper divergence will
    # drift this but is fine for sanity caps.
    cash = ps.get_cash()
    positions = {p.ticker: p for p in ps.list_positions()}
    pos = positions.get(ticker)
    equity = cash + sum(p.qty * p.avg_cost for p in positions.values())

    rsi = None
    try:
        df = ms.fetch_price_df(ticker, period="1mo", interval="1d")
        if df is not None and not df.empty:
            df = ms.add_advanced_indicators(df)
            val = df.iloc[-1].get("RSI")
            if val is not None and val == val:
                rsi = float(val)
    except Exception:
        rsi = None

    ref_price = req.price or 0.0
    if ref_price <= 0:
        df = ms.fetch_price_df(ticker, period="5d", interval="1d")
        ref_price = float(df.iloc[-1]["Close"]) if df is not None and not df.empty else 0.0
    if ref_price <= 0:
        raise HTTPException(status_code=400, detail=f"Can't price {ticker} for guardrails")

    decision = gr.check_order(
        ticker=ticker, side=req.side, qty=req.qty, price=ref_price,
        equity=equity, current_position_qty=pos.qty if pos else 0.0, rsi=rsi,
    )
    if not decision.allowed:
        notify.on_guardrail_block(ticker, decision.code, decision.reason)
        raise HTTPException(status_code=403, detail={"code": decision.code, "message": decision.reason})

    try:
        order = lb.place_order(
            ticker=ticker, side=req.side, qty=req.qty,
            order_type=req.order_type, price=req.price,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    gr.record_fill()
    fill_price = ref_price if order.executed_qty == 0 else (
        order.cummulative_quote_qty / order.executed_qty if order.executed_qty > 0 else ref_price
    )
    notify.on_paper_trade(ticker, order.side.lower(), order.qty, fill_price)
    return LiveOrderOut(**order.__dict__)


@router.get("/live/orders", response_model=List[LiveOrderOut])
def open_orders(ticker: Optional[str] = None) -> List[LiveOrderOut]:
    if not lb.is_enabled():
        return []
    try:
        orders = lb.open_orders(ticker=ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return [LiveOrderOut(**o.__dict__) for o in orders]


@router.delete("/live/orders/{ticker}/{order_id}", response_model=LiveOrderOut)
def cancel(ticker: str, order_id: int) -> LiveOrderOut:
    if not lb.is_enabled():
        raise HTTPException(status_code=403, detail="Binance testnet broker not configured")
    try:
        order = lb.cancel_order(ticker.upper(), order_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return LiveOrderOut(**order.__dict__)
