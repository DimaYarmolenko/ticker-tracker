from datetime import datetime
from typing import TypedDict

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.orm import Session

from app.models import Article, ArticleTicker
from app.repository.ticker import get_by_symbol

_CHART_MARKER_LIMIT = 500


class ArticleData(TypedDict):
    url: str
    title: str
    summary: str | None
    source: str | None
    published_at: datetime | None
    ticker_symbols: list[str]


def get_article_by_url(db: Session, url: str) -> Article | None:
    return db.query(Article).filter(Article.url == url).first()


def get_evaluated_articles_for_chart(
    db: Session, ticker_id: str, *, since: datetime, limit: int = _CHART_MARKER_LIMIT
) -> list[tuple[Article, ArticleTicker]]:
    # `since` must be naive UTC to match Article.published_at's column type (DateTime, no tz).

    stmt = (
        sa_select(Article, ArticleTicker)
        .join(ArticleTicker, Article.id == ArticleTicker.article_id)
        .where(
            ArticleTicker.ticker_id == ticker_id,
            Article.importance.is_not(None),
            ArticleTicker.impact.is_not(None),
            Article.published_at.is_not(None),
            Article.published_at >= since,
        )
        .order_by(Article.published_at.asc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [(row[0], row[1]) for row in rows]


def get_articles_page(
    db: Session, ticker_id: str, limit: int = 20, offset: int = 0
) -> tuple[list[tuple[Article, ArticleTicker]], int]:
    count_sub = (
        sa_select(func.count(Article.id))
        .join(ArticleTicker, Article.id == ArticleTicker.article_id)
        .where(ArticleTicker.ticker_id == ticker_id)
        .scalar_subquery()
    )
    stmt = (
        sa_select(Article, ArticleTicker, count_sub.label("total"))
        .join(ArticleTicker, Article.id == ArticleTicker.article_id)
        .where(ArticleTicker.ticker_id == ticker_id)
        .order_by(Article.published_at.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    if rows:
        return [(row[0], row[1]) for row in rows], rows[0][2]
    total = db.scalar(
        sa_select(func.count(Article.id))
        .join(ArticleTicker, Article.id == ArticleTicker.article_id)
        .where(ArticleTicker.ticker_id == ticker_id)
    )
    return [], total or 0


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
