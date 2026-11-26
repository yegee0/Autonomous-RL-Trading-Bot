import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.services.binance_ws import stream_klines, ticker_to_binance_symbol
from backend.app.services.orderbook_ws import (
    stream_depth,
    stream_liquidations,
    ticker_to_binance_spot,
)

router = APIRouter()
log = logging.getLogger("live")


async def _pump(websocket: WebSocket, stream) -> None:
    """Pump an async-iterator to the websocket; break on disconnect/send failure."""
    try:
        async for msg in stream:
            try:
                await websocket.send_text(json.dumps(msg))
            except WebSocketDisconnect:
                break
            except Exception as e:
                log.warning("send failed: %s", e)
                break
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/live/{ticker}")
async def live_feed(websocket: WebSocket, ticker: str, interval: str = "1m"):
    await websocket.accept()
    ticker = ticker.upper().strip()
    symbol = ticker_to_binance_symbol(ticker)

    if not symbol:
        await websocket.send_json({"error": f"{ticker} is not a crypto pair; use polling instead."})
        await websocket.close(code=1003)
        return

    await _pump(websocket, stream_klines(ticker, interval=interval))


@router.websocket("/ws/depth/{ticker}")
async def depth_feed(websocket: WebSocket, ticker: str, levels: int = 20):
    await websocket.accept()
    ticker = ticker.upper().strip()
    if not ticker_to_binance_spot(ticker):
        await websocket.send_json({"error": f"{ticker} has no depth stream."})
        await websocket.close(code=1003)
        return
    await _pump(websocket, stream_depth(ticker, levels=levels))


@router.websocket("/ws/liquidations/{ticker}")
async def liquidations_feed(websocket: WebSocket, ticker: str):
    await websocket.accept()
    ticker = ticker.upper().strip()
    if not ticker_to_binance_spot(ticker):
        await websocket.send_json({"error": f"{ticker} has no liquidation stream."})
        await websocket.close(code=1003)
        return
    await _pump(websocket, stream_liquidations(ticker))
