import logging
import os
from datetime import datetime, timezone
from enum import StrEnum

from apscheduler.schedulers.background import BackgroundScheduler

import app.repository as repo
from app.database import db_session
from app.news_fetcher import fetch_news
from app.price_fetcher import fetch_prices

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


class SchedulerJobId(StrEnum):
    NEWS_POLL = "news_poll"
    PRICE_POLL = "price_poll"


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


def start_scheduler() -> None:
    global _scheduler
    if not (raw_news := os.getenv("NEWS_POLL_INTERVAL_MINUTES")):
        raise ValueError("NEWS_POLL_INTERVAL_MINUTES env var is required")
    try:
        news_interval = int(raw_news)
    except ValueError:
        raise ValueError(
            f"NEWS_POLL_INTERVAL_MINUTES must be a valid integer, got: {raw_news!r}"
        ) from None

    if not (raw_price := os.getenv("PRICE_POLL_INTERVAL_MINUTES")):
        raise ValueError("PRICE_POLL_INTERVAL_MINUTES env var is required")
    try:
        price_interval = int(raw_price)
    except ValueError:
        raise ValueError(
            f"PRICE_POLL_INTERVAL_MINUTES must be a valid integer, got: {raw_price!r}"
        ) from None

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
    _scheduler.start()
    logger.info("Scheduler started (news: %d min, prices: %d min)", news_interval, price_interval)


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
