from datetime import datetime
from typing import TypedDict

from sqlalchemy.orm import Query, Session

from app.models import Article, article_tickers
from app.repository.ticker import get_by_symbol


class ArticleData(TypedDict):
    url: str
    title: str
    summary: str | None
    source: str | None
    published_at: datetime | None
    ticker_symbols: list[str]


def get_article_by_url(db: Session, url: str) -> Article | None:
    return db.query(Article).filter(Article.url == url).first()


def _articles_for_ticker_query(db: Session, ticker_id: str) -> Query[Article]:
    return (
        db.query(Article)
        .join(article_tickers, Article.id == article_tickers.c.article_id)
        .filter(article_tickers.c.ticker_id == ticker_id)
        .order_by(Article.published_at.desc().nulls_last())
    )


def get_articles_by_ticker_id(
    db: Session, ticker_id: str, limit: int = 20, offset: int = 0
) -> list[Article]:
    return _articles_for_ticker_query(db, ticker_id).offset(offset).limit(limit).all()


def count_articles_by_ticker_id(db: Session, ticker_id: str) -> int:
    return _articles_for_ticker_query(db, ticker_id).count()


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
