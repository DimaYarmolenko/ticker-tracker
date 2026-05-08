from typing import TypedDict

from sqlalchemy.orm import Query, Session

from app.models import Price, Ticker


class PriceData(TypedDict):
    symbol: str
    price: float
    open: float | None
    high: float | None
    low: float | None
    volume: int | None


def _prices_for_ticker_query(db: Session, ticker_id: str) -> Query[Price]:
    return db.query(Price).filter(Price.ticker_id == ticker_id).order_by(Price.fetched_at.desc())


def get_prices_by_ticker_id(
    db: Session, ticker_id: str, limit: int = 20, offset: int = 0
) -> list[Price]:
    return _prices_for_ticker_query(db, ticker_id).offset(offset).limit(limit).all()


def count_prices_by_ticker_id(db: Session, ticker_id: str) -> int:
    return _prices_for_ticker_query(db, ticker_id).count()


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
