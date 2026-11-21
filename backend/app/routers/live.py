import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.services.binance_ws import stream_klines, ticker_to_binance_symbol

router = APIRouter()
log = logging.getLogger("live")


@router.websocket("/ws/live/{ticker}")
async def live_feed(websocket: WebSocket, ticker: str, interval: str = "1m"):
    await websocket.accept()
    ticker = ticker.upper().strip()
    symbol = ticker_to_binance_symbol(ticker)

    if not symbol:
        await websocket.send_json({"error": f"{ticker} is not a crypto pair; use polling instead."})
        await websocket.close(code=1003)
        return

    try:
        async for kline in stream_klines(ticker, interval=interval):
            try:
                await websocket.send_text(json.dumps(kline))
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
