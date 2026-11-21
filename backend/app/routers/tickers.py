import os
from typing import List

from fastapi import APIRouter

from backend.app.schemas.market import TickerMeta

router = APIRouter()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "trained")

CATALOG = [
    ("BTC-USD", "Bitcoin", "crypto"),
    ("ETH-USD", "Ethereum", "crypto"),
    ("SOL-USD", "Solana", "crypto"),
    ("AAPL", "Apple Inc.", "stock"),
    ("TSLA", "Tesla Inc.", "stock"),
    ("MSFT", "Microsoft Corp.", "stock"),
    ("NVDA", "NVIDIA Corp.", "stock"),
    ("GOOGL", "Alphabet Inc.", "stock"),
    ("THYAO.IS", "Türk Hava Yolları", "bist"),
    ("ASELS.IS", "Aselsan", "bist"),
    ("GARAN.IS", "Garanti Bankası", "bist"),
]


def _model_path(ticker: str) -> str:
    safe = ticker.replace("-", "_").replace(".", "_")
    return os.path.join(MODELS_DIR, f"model_{safe}.zip")


@router.get("/tickers", response_model=List[TickerMeta])
def list_tickers() -> List[TickerMeta]:
    general_model = os.path.exists(os.path.join(MODELS_DIR, "model_general.zip"))
    out: List[TickerMeta] = []
    for symbol, name, klass in CATALOG:
        has_specific = os.path.exists(_model_path(symbol))
        out.append(
            TickerMeta(
                symbol=symbol,
                name=name,
                asset_class=klass,
                model_available=has_specific or general_model,
            )
        )
    return out
