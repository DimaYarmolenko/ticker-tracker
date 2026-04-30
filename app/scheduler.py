import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

import app.repository as repo
from app.database import SessionLocal
from app.news_fetcher import fetch_news

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _poll_news() -> None:
    db: Session = SessionLocal()
    try:
        tickers = repo.get_all(db)
        symbols = [t.symbol for t in tickers]
        if not symbols:
            logger.debug("No tickers tracked; skipping news poll")
            return
        logger.info("Polling news for %d ticker(s): %s", len(symbols), symbols)
        articles = fetch_news(symbols)
        if articles:
            repo.upsert_articles(db, articles)
            logger.info("Upserted %d article(s)", len(articles))
        else:
            logger.debug("No new articles found")
    except Exception:
        logger.exception("Unexpected error during news poll")
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if not (raw := os.getenv("NEWS_POLL_INTERVAL_MINUTES")):
        raise ValueError("NEWS_POLL_INTERVAL_MINUTES env var is required")
    try:
        interval = int(raw)
    except ValueError:
        raise ValueError(
            f"NEWS_POLL_INTERVAL_MINUTES must be a valid integer, got: {raw!r}"
        ) from None
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _poll_news,
        "interval",
        minutes=interval,
        id="news_poll",
        next_run_time=datetime.now(timezone.utc),
    )
    _scheduler.start()
    logger.info("News scheduler started (interval: %d min)", interval)


def stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("News scheduler stopped")
