from datetime import datetime
from typing import TypedDict

from sqlalchemy.orm import Query, Session

from app.models import Article, Price, Ticker, article_tickers


class ArticleData(TypedDict):
    url: str
    title: str
    summary: str | None
    source: str | None
    published_at: datetime | None
    ticker_symbols: list[str]


class PriceData(TypedDict):
    symbol: str
    price: float
    open: float | None
    high: float | None
    low: float | None
    volume: int | None


def get_all(db: Session) -> list[Ticker]:
    return db.query(Ticker).all()


def get_by_symbol(db: Session, symbol: str) -> Ticker | None:
    return db.query(Ticker).filter(Ticker.symbol == symbol).first()


def create(db: Session, symbol: str) -> Ticker:
    ticker = Ticker(symbol=symbol)
    db.add(ticker)
    db.commit()
    db.refresh(ticker)
    return ticker


def delete(db: Session, ticker: Ticker) -> None:
    db.delete(ticker)
    db.commit()


def get_article_by_url(db: Session, url: str) -> Article | None:
    return db.query(Article).filter(Article.url == url).first()


def _articles_for_ticker_query(db: Session, ticker_id: str) -> Query[Article]:
    return (
        db.query(Article)
        .join(article_tickers, Article.id == article_tickers.c.article_id)
        .filter(article_tickers.c.ticker_id == ticker_id)
        .order_by(Article.published_at.desc().nulls_last())
    )


def get_articles_by_symbol(
    db: Session, symbol: str, limit: int = 20, offset: int = 0
) -> list[Article]:
    ticker = get_by_symbol(db, symbol)
    if ticker is None:
        return []
    return _articles_for_ticker_query(db, ticker.id).offset(offset).limit(limit).all()


def count_articles_by_symbol(db: Session, symbol: str) -> int:
    ticker = get_by_symbol(db, symbol)
    if ticker is None:
        return 0
    return _articles_for_ticker_query(db, ticker.id).count()


def upsert_articles(db: Session, articles_data: list[ArticleData]) -> None:
    for data in articles_data:
        existing = get_article_by_url(db, data["url"])
        if existing:
            _attach_tickers(db, existing, data["ticker_symbols"])
            continue
        article = Article(
            url=data["url"],
            title=data["title"],
            summary=data.get("summary"),
            source=data.get("source"),
            published_at=data.get("published_at"),
        )
        db.add(article)
        db.flush()
        _attach_tickers(db, article, data["ticker_symbols"])
    db.commit()


def _attach_tickers(db: Session, article: Article, symbols: list[str]) -> None:
    existing_symbols = {t.symbol for t in article.tickers}
    for symbol in symbols:
        if symbol not in existing_symbols:
            ticker = get_by_symbol(db, symbol)
            if ticker:
                article.tickers.append(ticker)


def _prices_for_ticker_query(db: Session, ticker_id: str) -> Query[Price]:
    return db.query(Price).filter(Price.ticker_id == ticker_id).order_by(Price.fetched_at.desc())


def get_prices_by_symbol(db: Session, symbol: str, limit: int = 20, offset: int = 0) -> list[Price]:
    ticker = get_by_symbol(db, symbol)
    if ticker is None:
        return []
    return _prices_for_ticker_query(db, ticker.id).offset(offset).limit(limit).all()


def count_prices_by_symbol(db: Session, symbol: str) -> int:
    ticker = get_by_symbol(db, symbol)
    if ticker is None:
        return 0
    return _prices_for_ticker_query(db, ticker.id).count()


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
