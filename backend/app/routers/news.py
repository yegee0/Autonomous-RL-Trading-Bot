from typing import List

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.market import NewsItem
from backend.app.services import market_service as ms

router = APIRouter()


@router.get("/news/{ticker}", response_model=List[NewsItem])
def get_news(ticker: str, limit: int = Query(8, ge=1, le=20)) -> List[NewsItem]:
    ticker = ticker.upper().strip()
    try:
        items, _ = ms.fetch_news(ticker, limit=limit)
        return items
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"News fetch failed: {e}")
