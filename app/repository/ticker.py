from sqlalchemy.orm import Session

from app.models import Ticker


def get_all(db: Session) -> list[Ticker]:
    return db.query(Ticker).all()


def get_by_symbol(db: Session, symbol: str) -> Ticker | None:
    return db.query(Ticker).filter(Ticker.symbol == symbol).first()


def get_or_create(db: Session, symbol: str) -> Ticker:
    existing = get_by_symbol(db, symbol)
    if existing is not None:
        return existing
    ticker = Ticker(symbol=symbol)
    db.add(ticker)
    db.commit()
    db.refresh(ticker)
    return ticker
