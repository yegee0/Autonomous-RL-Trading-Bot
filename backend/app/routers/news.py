from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas.market import NewsFeed
from backend.app.services import market_service as ms

router = APIRouter()


@router.get("/news/{ticker}", response_model=NewsFeed)
def get_news(
    ticker: str,
    limit: int = Query(8, ge=1, le=25),
    reddit: bool = Query(True, description="Include Reddit posts"),
) -> NewsFeed:
    ticker = ticker.upper().strip()
    try:
        return ms.fetch_news(ticker, limit=limit, include_reddit=reddit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"News fetch failed: {e}")
