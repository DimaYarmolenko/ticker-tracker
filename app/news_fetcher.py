import logging
import os
import re
from datetime import datetime, timedelta, timezone

import feedparser
import httpx

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


def _get_max_age_days() -> int:
    try:
        return int(os.getenv("NEWS_MAX_AGE_DAYS", "2"))
    except ValueError:
        return 2


def _parse_entry(entry: dict) -> tuple[str, str, str | None, str | None, datetime | None]:
    url = entry.get("link", "")
    title = entry.get("title", "")
    summary = entry.get("summary") or None
    source_data = entry.get("source") or {}
    source = source_data.get("title") or None
    published_parsed = entry.get("published_parsed")
    published_at: datetime | None = None
    if published_parsed:
        published_at = datetime(*published_parsed[:6], tzinfo=timezone.utc)
    return url, title, summary, source, published_at


def fetch_news(symbols: list[str]) -> list[dict]:
    """
    Fetch recent news articles for the given ticker symbols via Google News RSS.
    Articles older than NEWS_MAX_AGE_DAYS are skipped.
    Duplicate URLs across multiple ticker fetches are merged into a single article
    with all relevant tickers. Article titles are also scanned for cross-mentions
    of other tracked symbols.
    Returns a list of dicts ready for repository.upsert_articles().
    """
    if not symbols:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=_get_max_age_days())
    symbols_set = set(symbols)
    seen: dict[str, dict] = {}

    for symbol in symbols:
        params = {
            "q": f"{symbol} stock",
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
        try:
            response = httpx.get(
                _GOOGLE_NEWS_RSS_URL,
                params=params,
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ticker-tracker/1.0)"},
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch news for %s: %s", symbol, exc)
            continue

        for entry in feed.entries:
            url, title, summary, source, published_at = _parse_entry(entry)
            if not url or not title:
                continue
            if published_at is not None and published_at < cutoff:
                continue

            if url in seen:
                if symbol not in seen[url]["ticker_symbols"]:
                    seen[url]["ticker_symbols"].append(symbol)
            else:
                seen[url] = {
                    "url": url,
                    "title": title,
                    "summary": summary,
                    "source": source,
                    "published_at": published_at,
                    "ticker_symbols": [symbol],
                }

    for article in seen.values():
        title_upper = article["title"].upper()
        for sym in symbols_set:
            if sym not in article["ticker_symbols"]:
                if re.search(r"\b" + re.escape(sym) + r"\b", title_upper):
                    article["ticker_symbols"].append(sym)

    return list(seen.values())
