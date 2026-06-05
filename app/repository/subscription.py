from sqlalchemy.orm import Session

from app.models import Ticker, UserTicker


def list_subscribed_tickers(db: Session, user_id: str) -> list[Ticker]:
    return (
        db.query(Ticker)
        .join(UserTicker, UserTicker.ticker_id == Ticker.id)
        .filter(UserTicker.user_id == user_id)
        .order_by(UserTicker.subscribed_at)
        .all()
    )


def is_subscribed(db: Session, user_id: str, ticker_id: str) -> bool:
    return (
        db.query(UserTicker)
        .filter(UserTicker.user_id == user_id, UserTicker.ticker_id == ticker_id)
        .first()
        is not None
    )


def subscribe(db: Session, user_id: str, ticker: Ticker) -> bool:
    """Subscribe a user to a ticker. Returns False if already subscribed."""
    if is_subscribed(db, user_id, ticker.id):
        return False
    db.add(UserTicker(user_id=user_id, ticker_id=ticker.id))
    db.commit()
    return True


def unsubscribe(db: Session, user_id: str, ticker_id: str) -> bool:
    """Remove a user's subscription to a ticker. Returns False if not subscribed."""
    row = (
        db.query(UserTicker)
        .filter(UserTicker.user_id == user_id, UserTicker.ticker_id == ticker_id)
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True
