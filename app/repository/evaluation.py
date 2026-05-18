import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.evaluator import ArticleEvaluation
from app.models import Article, ArticleTicker, Ticker

logger = logging.getLogger(__name__)


def get_unevaluated_articles(db: Session, limit: int) -> list[Article]:
    has_ticker = (
        select(ArticleTicker.article_id).where(ArticleTicker.article_id == Article.id).exists()
    )
    stmt = (
        select(Article)
        .where(Article.evaluated_at.is_(None))
        .where(has_ticker)
        .options(selectinload(Article.tickers))
        .order_by(Article.published_at.desc().nulls_last())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def save_evaluations(db: Session, results: list[ArticleEvaluation], version: str) -> None:
    if not results:
        return

    article_ids = [r.article_id for r in results]
    articles_by_id = {
        a.id: a for a in db.scalars(select(Article).where(Article.id.in_(article_ids)))
    }

    symbols_needed = {imp.symbol for r in results for imp in r.impacts}
    tickers_by_symbol: dict[str, Ticker] = {}
    if symbols_needed:
        tickers_by_symbol = {
            t.symbol: t for t in db.scalars(select(Ticker).where(Ticker.symbol.in_(symbols_needed)))
        }

    links_by_key: dict[tuple[str, str], ArticleTicker] = {
        (link.article_id, link.ticker_id): link
        for link in db.scalars(
            select(ArticleTicker).where(ArticleTicker.article_id.in_(article_ids))
        )
    }

    now = datetime.now(timezone.utc)
    for result in results:
        article = articles_by_id.get(result.article_id)
        if article is None:
            logger.warning("Evaluation result for unknown article_id %s", result.article_id)
            continue
        article.importance = result.importance
        article.evaluated_at = now
        article.evaluator_version = version

        for impact in result.impacts:
            ticker = tickers_by_symbol.get(impact.symbol)
            if ticker is None:
                logger.warning(
                    "Evaluation impact for unknown ticker %s on article %s; dropping",
                    impact.symbol,
                    article.id,
                )
                continue
            link = links_by_key.get((article.id, ticker.id))
            if link is None:
                logger.warning(
                    "No article_ticker link for article %s / %s; dropping impact",
                    article.id,
                    impact.symbol,
                )
                continue
            link.impact = impact.impact
            link.impact_confidence = impact.confidence

    db.commit()
