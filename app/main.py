import logging
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.orm import Session

import app.repository as repo
from app.database import Base, engine, get_db
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Ticker Tracker", lifespan=lifespan)


@app.get("/tickers", response_model=list[TickerResponse])
def list_tickers(db: Session = Depends(get_db)):
    return repo.get_all(db)


@app.post("/tickers", response_model=TickerResponse, status_code=status.HTTP_201_CREATED)
def add_ticker(payload: TickerCreate, db: Session = Depends(get_db)):
    if repo.get_by_symbol(db, payload.symbol):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{payload.symbol} already exists",
        )
    return repo.create(db, payload.symbol)


@app.delete("/tickers/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticker(symbol: str, db: Session = Depends(get_db)):
    ticker = repo.get_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol.upper()} not found",
        )
    repo.delete(db, ticker)


@app.get("/tickers/{symbol}/news", response_model=ArticleListResponse)
def get_ticker_news(
    symbol: str,
    pagination: Annotated[PaginationParams, Query()],
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()
    ticker = repo.get_by_symbol(db, symbol)
    if not ticker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol} not found",
        )
    articles, total = repo.get_articles_page(
        db, ticker.id, limit=pagination.limit, offset=pagination.offset
    )
    return ArticleListResponse(
        ticker=symbol,
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        articles=[ArticleResponse.model_validate(article) for article in articles],
    )


@app.get("/tickers/{symbol}/prices", response_model=PriceListResponse)
def get_ticker_prices(
    symbol: str,
    pagination: Annotated[PaginationParams, Query()],
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()
    ticker = repo.get_by_symbol(db, symbol)
    if not ticker:
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
