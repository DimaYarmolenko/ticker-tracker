from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.repository as repo
from app.evaluator import ArticleEvaluation, TickerImpact
from app.models import Article, ImpactLabel


def _evaluate_all(db_session: Session, impact: ImpactLabel = ImpactLabel.POSITIVE) -> None:
    """Mark every article + every (article, ticker) link as evaluated."""
    articles = db_session.scalars(select(Article)).all()
    evaluations: list[ArticleEvaluation] = []
    for article in articles:
        evaluations.append(
            ArticleEvaluation(
                article_id=article.id,
                importance=3,
                impacts=[
                    TickerImpact(symbol=t.symbol, impact=impact, confidence=0.8)
                    for t in article.tickers
                ],
            )
        )
    repo.save_evaluations(db_session, evaluations, version="v1")


def test_get_evaluated_articles_for_chart_returns_evaluated_links(
    db_session: Session, seeded_articles: None
) -> None:
    _evaluate_all(db_session)
    aapl = repo.get_by_symbol(db_session, "AAPL")
    assert aapl is not None

    rows = repo.get_evaluated_articles_for_chart(
        db_session, aapl.id, since=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert len(rows) == 2
    assert all(article.importance is not None for article, _ in rows)
    assert all(link.impact is not None for _, link in rows)


def test_get_evaluated_articles_for_chart_skips_unevaluated(
    db_session: Session, seeded_articles: None
) -> None:
    aapl = repo.get_by_symbol(db_session, "AAPL")
    assert aapl is not None

    rows = repo.get_evaluated_articles_for_chart(
        db_session, aapl.id, since=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert rows == []


def test_get_evaluated_articles_for_chart_filters_by_ticker(
    db_session: Session, seeded_articles: None
) -> None:
    _evaluate_all(db_session)
    msft = repo.get_by_symbol(db_session, "MSFT")
    assert msft is not None

    rows = repo.get_evaluated_articles_for_chart(
        db_session, msft.id, since=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    # Only the "tech giants" article links MSFT; the Apple-only article should be absent.
    assert len(rows) == 1
    article, _ = rows[0]
    assert article.url == "https://example.com/tech-giants-article"


def test_get_evaluated_articles_for_chart_respects_since(
    db_session: Session, seeded_articles: None
) -> None:
    _evaluate_all(db_session)
    aapl = repo.get_by_symbol(db_session, "AAPL")
    assert aapl is not None

    # Seeded articles are published 2026-04-28; cut off after that date.
    rows = repo.get_evaluated_articles_for_chart(
        db_session, aapl.id, since=datetime(2026, 5, 1, tzinfo=timezone.utc)
    )

    assert rows == []


def test_get_evaluated_articles_for_chart_orders_ascending(
    db_session: Session, seeded_articles: None
) -> None:
    _evaluate_all(db_session)
    aapl = repo.get_by_symbol(db_session, "AAPL")
    assert aapl is not None

    rows = repo.get_evaluated_articles_for_chart(
        db_session, aapl.id, since=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    published = [article.published_at for article, _ in rows]
    assert published == sorted(published)


def test_get_evaluated_articles_for_chart_respects_limit(
    db_session: Session, seeded_articles: None
) -> None:
    _evaluate_all(db_session)
    aapl = repo.get_by_symbol(db_session, "AAPL")
    assert aapl is not None

    rows = repo.get_evaluated_articles_for_chart(
        db_session, aapl.id, since=datetime(2026, 1, 1, tzinfo=timezone.utc), limit=1
    )

    assert len(rows) == 1


def test_get_evaluated_articles_for_chart_skips_null_published_at(
    db_session: Session, seeded_tickers: list
) -> None:
    """Articles without a published_at cannot be plotted and must be excluded."""
    repo.upsert_articles(
        db_session,
        [
            {
                "url": "https://example.com/no-date",
                "title": "Undated",
                "summary": None,
                "source": None,
                "published_at": None,
                "ticker_symbols": ["AAPL"],
            }
        ],
    )
    _evaluate_all(db_session)
    aapl = repo.get_by_symbol(db_session, "AAPL")
    assert aapl is not None

    rows = repo.get_evaluated_articles_for_chart(
        db_session,
        aapl.id,
        since=datetime.now(timezone.utc) - timedelta(days=365),
    )

    assert all(article.published_at is not None for article, _ in rows)
