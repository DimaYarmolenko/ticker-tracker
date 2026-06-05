import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

import app.repository as repo
from app.auth import current_user
from app.auth_routes import router as auth_router
from app.database import get_db
from app.models import User
from app.scheduler import start_scheduler, stop_scheduler
from app.schemas import (
    ArticleListResponse,
    ArticleResponse,
    PaginationParams,
    PriceListResponse,
    PriceResponse,
    TickerCreate,
    TickerResponse,
)
from app.ui import router as ui_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    start_scheduler()
    yield
    stop_scheduler()


_STATIC_DIR = Path(__file__).resolve().parent / "static"
_SESSION_SECRET = os.environ["SESSION_SECRET_KEY"]

app = FastAPI(title="Ticker Tracker", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=_SESSION_SECRET, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
app.include_router(auth_router)
app.include_router(ui_router)


@app.get("/tickers", response_model=list[TickerResponse])
def list_tickers(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return repo.list_subscribed_tickers(db, user.id)


@app.post("/tickers", response_model=TickerResponse, status_code=status.HTTP_201_CREATED)
def add_ticker(
    payload: TickerCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    ticker = repo.get_or_create(db, payload.symbol)
    if not repo.subscribe(db, user.id, ticker):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{payload.symbol} already exists",
        )
    return ticker


@app.delete("/tickers/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticker(
    symbol: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()
    ticker = repo.get_by_symbol(db, symbol)
    if not ticker or not repo.unsubscribe(db, user.id, ticker.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol} not found",
        )


@app.get("/tickers/{symbol}/news", response_model=ArticleListResponse)
def get_ticker_news(
    symbol: str,
    pagination: Annotated[PaginationParams, Query()],
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()
    ticker = repo.get_by_symbol(db, symbol)
    if not ticker or not repo.is_subscribed(db, user.id, ticker.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol} not found",
        )
    rows, total = repo.get_articles_page(
        db, ticker.id, limit=pagination.limit, offset=pagination.offset
    )
    return ArticleListResponse(
        ticker=symbol,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        articles=[
            ArticleResponse(
                id=article.id,
                url=article.url,
                title=article.title,
                summary=article.summary,
                source=article.source,
                published_at=article.published_at,
                fetched_at=article.fetched_at,
                importance=article.importance,
                evaluated_at=article.evaluated_at,
                impact=link.impact,
                impact_confidence=link.impact_confidence,
            )
            for article, link in rows
        ],
    )


@app.get("/tickers/{symbol}/prices", response_model=PriceListResponse)
def get_ticker_prices(
    symbol: str,
    pagination: Annotated[PaginationParams, Query()],
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()
    ticker = repo.get_by_symbol(db, symbol)
    if not ticker or not repo.is_subscribed(db, user.id, ticker.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol} not found",
        )
    prices, total = repo.get_prices_page(
        db, ticker.id, limit=pagination.limit, offset=pagination.offset
    )
    return PriceListResponse(
        ticker=symbol,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        prices=[PriceResponse.model_validate(p) for p in prices],
    )
