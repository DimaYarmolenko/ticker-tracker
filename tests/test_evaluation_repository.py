from sqlalchemy import select
from sqlalchemy.orm import Session

import app.repository as repo
from app.evaluator import ArticleEvaluation, TickerImpact
from app.models import Article, ArticleTicker, ImpactLabel

# --- get_unevaluated_articles ---


def test_get_unevaluated_articles_returns_articles_with_tickers(
    db_session: Session, seeded_articles: None
) -> None:
    result = repo.get_unevaluated_articles(db_session, limit=10)
    assert len(result) == 2
    assert all(a.evaluated_at is None for a in result)


def test_get_unevaluated_articles_skips_articles_without_tickers(
    db_session: Session, seeded_tickers: list
) -> None:
    orphan = Article(url="https://x.com/orphan", title="orphan")
    db_session.add(orphan)
    db_session.commit()
    result = repo.get_unevaluated_articles(db_session, limit=10)
    assert all(a.id != orphan.id for a in result)


def test_get_unevaluated_articles_skips_already_evaluated(
    db_session: Session, seeded_articles: None
) -> None:
    article = db_session.scalars(select(Article).limit(1)).one()
    repo.save_evaluations(
        db_session,
        [ArticleEvaluation(article_id=article.id, importance=3, impacts=[])],
        version="v1",
    )

    result = repo.get_unevaluated_articles(db_session, limit=10)
    assert all(a.id != article.id for a in result)


def test_get_unevaluated_articles_respects_limit(
    db_session: Session, seeded_articles: None
) -> None:
    result = repo.get_unevaluated_articles(db_session, limit=1)
    assert len(result) == 1


# --- save_evaluations ---


def test_save_evaluations_sets_article_fields(db_session: Session, seeded_articles: None) -> None:
    article = db_session.scalars(select(Article).limit(1)).one()
    repo.save_evaluations(
        db_session,
        [
            ArticleEvaluation(
                article_id=article.id,
                importance=4,
                impacts=[],
            )
        ],
        version="v7",
    )

    db_session.refresh(article)
    assert article.importance == 4
    assert article.evaluated_at is not None
    assert article.evaluator_version == "v7"


def test_save_evaluations_sets_per_ticker_impact(
    db_session: Session, seeded_articles: None
) -> None:
    article = db_session.scalars(
        select(Article).where(Article.url == "https://example.com/tech-giants-article")
    ).one()

    repo.save_evaluations(
        db_session,
        [
            ArticleEvaluation(
                article_id=article.id,
                importance=5,
                impacts=[
                    TickerImpact(symbol="AAPL", impact=ImpactLabel.POSITIVE, confidence=0.9),
                    TickerImpact(symbol="MSFT", impact=ImpactLabel.NEGATIVE, confidence=0.6),
                ],
            )
        ],
        version="v1",
    )

    links = db_session.scalars(
        select(ArticleTicker).where(ArticleTicker.article_id == article.id)
    ).all()
    by_ticker_symbol = {link.ticker_id: link for link in links}
    aapl_id = next(t.id for t in article.tickers if t.symbol == "AAPL")
    msft_id = next(t.id for t in article.tickers if t.symbol == "MSFT")

    assert by_ticker_symbol[aapl_id].impact == ImpactLabel.POSITIVE
    assert by_ticker_symbol[aapl_id].impact_confidence == 0.9
    assert by_ticker_symbol[msft_id].impact == ImpactLabel.NEGATIVE
    assert by_ticker_symbol[msft_id].impact_confidence == 0.6


def test_save_evaluations_unknown_article_id_is_skipped(
    db_session: Session, seeded_articles: None
) -> None:
    repo.save_evaluations(
        db_session,
        [ArticleEvaluation(article_id="does-not-exist", importance=3, impacts=[])],
        version="v1",
    )
    rows = db_session.scalars(select(Article)).all()
    assert all(a.evaluated_at is None for a in rows)


def test_save_evaluations_unknown_ticker_symbol_ignored(
    db_session: Session, seeded_articles: None
) -> None:
    article = db_session.scalars(select(Article).limit(1)).one()
    repo.save_evaluations(
        db_session,
        [
            ArticleEvaluation(
                article_id=article.id,
                importance=2,
                impacts=[
                    TickerImpact(symbol="GOOG", impact=ImpactLabel.POSITIVE, confidence=0.5),
                ],
            )
        ],
        version="v1",
    )
    db_session.refresh(article)
    assert article.importance == 2


def test_save_evaluations_empty_list_is_noop(db_session: Session) -> None:
    repo.save_evaluations(db_session, [], version="v1")
