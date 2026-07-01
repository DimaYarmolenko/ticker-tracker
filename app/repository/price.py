from typing import TypedDict

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.orm import Session

from app.models import Price, Ticker
from app.repository._pagination import paginate


class PriceData(TypedDict):
    symbol: str
    price: float
    open: float | None
    high: float | None
    low: float | None
    volume: int | None


def get_prices_page(
    db: Session, ticker_id: str, limit: int = 20, offset: int = 0
) -> tuple[list[Price], int]:
    base_stmt = (
        sa_select(Price).where(Price.ticker_id == ticker_id).order_by(Price.fetched_at.desc())
    )
    count_stmt = sa_select(func.count(Price.id)).where(Price.ticker_id == ticker_id)
    rows, total = paginate(db, base_stmt, count_stmt, limit=limit, offset=offset)
    return [row[0] for row in rows], total


def get_price_history(db: Session, ticker_id: str, limit: int = 2000) -> list[Price]:
    stmt = (
        sa_select(Price)
        .where(Price.ticker_id == ticker_id)
        .order_by(Price.fetched_at.desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars())
    rows.reverse()
    return rows


def insert_prices(db: Session, prices_data: list[PriceData]) -> None:
    if not prices_data:
        return
    symbols = [data["symbol"] for data in prices_data]
    ticker_map: dict[str, Ticker] = {
        t.symbol: t for t in db.query(Ticker).filter(Ticker.symbol.in_(symbols)).all()
    }
    for data in prices_data:
        ticker = ticker_map.get(data["symbol"])
        if ticker is None:
            continue
        db.add(
            Price(
                ticker_id=ticker.id,
                price=data["price"],
                open=data["open"],
                high=data["high"],
                low=data["low"],
                volume=data["volume"],
            )
        )
    db.commit()
