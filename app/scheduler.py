import logging
import os
from datetime import datetime, timezone
from enum import StrEnum

from apscheduler.schedulers.background import BackgroundScheduler

import app.repository as repo
from app.config import env_bool, read_int_env
from app.database import db_session
from app.evaluator import ArticleEvaluation, Evaluator, EvaluatorInput, get_evaluator
from app.news_fetcher import fetch_news
from app.price_fetcher import fetch_prices

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


class SchedulerJobId(StrEnum):
    NEWS_POLL = "news_poll"
    PRICE_POLL = "price_poll"
    EVALUATE = "evaluate_articles"


def _poll_news() -> None:
    try:
        with db_session() as db:
            symbols = [t.symbol for t in repo.get_all(db)]
    except Exception:
        logger.exception("Unexpected error reading tickers during news poll")
        return

    if not symbols:
        logger.debug("No tickers tracked; skipping news poll")
        return

    logger.info("Polling news for %d ticker(s): %s", len(symbols), symbols)
    try:
        articles = fetch_news(symbols)
    except Exception:
        logger.exception("Unexpected error fetching news")
        return

    if not articles:
        logger.debug("No new articles found")
        return

    try:
        with db_session() as db:
            repo.upsert_articles(db, articles)
            logger.info("Upserted %d article(s)", len(articles))
    except Exception:
        logger.exception("Unexpected error upserting articles during news poll")


def _poll_prices() -> None:
    try:
        with db_session() as db:
            symbols = [t.symbol for t in repo.get_all(db)]
    except Exception:
        logger.exception("Unexpected error reading tickers during price poll")
        return

    if not symbols:
        logger.debug("No tickers tracked; skipping price poll")
        return

    logger.info("Polling prices for %d ticker(s): %s", len(symbols), symbols)
    try:
        prices = fetch_prices(symbols)
    except Exception:
        logger.exception("Unexpected error fetching prices")
        return

    if not prices:
        logger.debug("No price data fetched")
        return

    try:
        with db_session() as db:
            repo.insert_prices(db, prices)
            logger.info("Inserted %d price snapshot(s)", len(prices))
    except Exception:
        logger.exception("Unexpected error inserting prices during price poll")


def _poll_evaluations(
    evaluator: Evaluator, version: str, batch_size: int, max_per_run: int
) -> None:
    try:
        with db_session() as db:
            articles = repo.get_unevaluated_articles(db, limit=max_per_run)
            if not articles:
                logger.debug("No unevaluated articles; skipping evaluation poll")
                return

            inputs = [
                EvaluatorInput(
                    article_id=a.id,
                    title=a.title,
                    summary=a.summary,
                    ticker_symbols=[t.symbol for t in a.tickers],
                )
                for a in articles
            ]

            logger.info("Evaluating %d article(s) in batches of %d", len(inputs), batch_size)
            all_results: list[ArticleEvaluation] = []
            for start in range(0, len(inputs), batch_size):
                batch = inputs[start : start + batch_size]
                all_results.extend(evaluator.evaluate(batch))

            if all_results:
                repo.save_evaluations(db, all_results, version)
                logger.info("Persisted evaluations for %d article(s)", len(all_results))
            else:
                logger.warning("Evaluator returned no results for %d article(s)", len(inputs))
    except Exception:
        logger.exception("Unexpected error during evaluation poll")


def _register_evaluation_job(scheduler: BackgroundScheduler) -> None:
    if not env_bool("EVALUATOR_ENABLED", default=False):
        logger.info("Evaluator disabled; skipping evaluation job registration")
        return

    eval_interval = read_int_env("EVALUATION_POLL_INTERVAL_MINUTES", required=True)
    batch_size = read_int_env("EVALUATOR_BATCH_SIZE", required=False, default=10)
    max_per_run = read_int_env("EVALUATOR_MAX_PER_RUN", required=False, default=100)
    version = os.getenv("EVALUATOR_VERSION", "v1")

    try:
        evaluator = get_evaluator()
    except Exception:
        logger.exception("Failed to initialize evaluator; evaluation job will not be registered")
        return

    scheduler.add_job(
        _poll_evaluations,
        "interval",
        minutes=eval_interval,
        id=SchedulerJobId.EVALUATE,
        next_run_time=datetime.now(timezone.utc),
        kwargs={
            "evaluator": evaluator,
            "version": version,
            "batch_size": batch_size,
            "max_per_run": max_per_run,
        },
    )
    logger.info(
        "Evaluator enabled (interval: %d min, batch: %d, max/run: %d, version: %s)",
        eval_interval,
        batch_size,
        max_per_run,
        version,
    )


def start_scheduler() -> None:
    global _scheduler
    news_interval = read_int_env("NEWS_POLL_INTERVAL_MINUTES", required=True)
    price_interval = read_int_env("PRICE_POLL_INTERVAL_MINUTES", required=True)

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _poll_news,
        "interval",
        minutes=news_interval,
        id=SchedulerJobId.NEWS_POLL,
        next_run_time=datetime.now(timezone.utc),
    )
    _scheduler.add_job(
        _poll_prices,
        "interval",
        minutes=price_interval,
        id=SchedulerJobId.PRICE_POLL,
        next_run_time=datetime.now(timezone.utc),
    )
    _register_evaluation_job(_scheduler)
    _scheduler.start()
    logger.info("Scheduler started (news: %d min, prices: %d min)", news_interval, price_interval)


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
