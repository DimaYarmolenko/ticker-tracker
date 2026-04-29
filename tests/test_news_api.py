from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.repository as repo
from app.models import Article

# --- GET /tickers/{symbol}/news endpoint tests ---


def test_get_ticker_news_returns_articles_for_ticker(
    client: TestClient, seeded_articles: None
) -> None:
    response = client.get("/tickers/AAPL/news")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["total"] == 2
    assert len(body["articles"]) == 2


def test_get_ticker_news_returns_only_linked_articles(
    client: TestClient, seeded_articles: None
) -> None:
    response = client.get("/tickers/MSFT/news")
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "MSFT"
    assert body["total"] == 1
    assert body["articles"][0]["title"] == "Tech giants rally"


def test_get_ticker_news_response_shape(client: TestClient, seeded_articles: None) -> None:
    response = client.get("/tickers/AAPL/news")
    body = response.json()
    for key in ("ticker", "total", "limit", "offset", "articles"):
        assert key in body
    article = body["articles"][0]
    for field in ("id", "url", "title", "summary", "source", "published_at", "fetched_at"):
        assert field in article


def test_get_ticker_news_pagination_limit(client: TestClient, seeded_articles: None) -> None:
    response = client.get("/tickers/AAPL/news?limit=1")
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert len(body["articles"]) == 1


def test_get_ticker_news_pagination_offset(client: TestClient, seeded_articles: None) -> None:
    resp_page1 = client.get("/tickers/AAPL/news?limit=1&offset=0")
    resp_page2 = client.get("/tickers/AAPL/news?limit=1&offset=1")
    url1 = resp_page1.json()["articles"][0]["url"]
    url2 = resp_page2.json()["articles"][0]["url"]
    assert url1 != url2


def test_get_ticker_news_offset_beyond_total_returns_empty(
    client: TestClient, seeded_articles: None
) -> None:
    response = client.get("/tickers/AAPL/news?offset=999")
    body = response.json()
    assert response.status_code == 200
    assert body["articles"] == []
    assert body["total"] == 2


def test_get_ticker_news_symbol_case_insensitive(client: TestClient, seeded_articles: None) -> None:
    response = client.get("/tickers/aapl/news")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"


def test_get_ticker_news_empty_when_no_articles(client: TestClient, seeded_tickers: list) -> None:
    response = client.get("/tickers/AAPL/news")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["articles"] == []


def test_get_ticker_news_unknown_symbol_returns_404(client: TestClient) -> None:
    response = client.get("/tickers/UNKNOWN/news")
    assert response.status_code == 404


def test_get_ticker_news_404_has_detail_field(client: TestClient) -> None:
    response = client.get("/tickers/FAKE/news")
    assert response.status_code == 404
    assert "detail" in response.json()


# --- upsert_articles repository tests ---


def test_upsert_articles_inserts_new_article(db_session: Session, seeded_tickers: list) -> None:
    articles_data = [
        {
            "url": "https://example.com/new",
            "title": "New article",
            "summary": None,
            "source": "TestSource",
            "published_at": datetime(2026, 4, 28, tzinfo=timezone.utc),
            "ticker_symbols": ["AAPL"],
        }
    ]
    repo.upsert_articles(db_session, articles_data)

    article = repo.get_article_by_url(db_session, "https://example.com/new")
    assert article is not None
    assert article.title == "New article"
    assert any(t.symbol == "AAPL" for t in article.tickers)


def test_upsert_articles_reinserting_same_url_adds_new_ticker(
    db_session: Session, seeded_tickers: list
) -> None:
    url = "https://example.com/shared"
    base = {"url": url, "title": "Shared", "summary": None, "source": None, "published_at": None}
    repo.upsert_articles(db_session, [{**base, "ticker_symbols": ["AAPL"]}])
    repo.upsert_articles(db_session, [{**base, "ticker_symbols": ["MSFT"]}])

    article = repo.get_article_by_url(db_session, url)
    assert {t.symbol for t in article.tickers} == {"AAPL", "MSFT"}


def test_upsert_articles_reinserting_same_url_no_duplicate_ticker(
    db_session: Session, seeded_tickers: list
) -> None:
    url = "https://example.com/aapl-dup"
    data = [
        {
            "url": url,
            "title": "AAPL article",
            "summary": None,
            "source": None,
            "published_at": None,
            "ticker_symbols": ["AAPL"],
        }
    ]
    repo.upsert_articles(db_session, data)
    repo.upsert_articles(db_session, data)

    article = repo.get_article_by_url(db_session, url)
    assert len([t for t in article.tickers if t.symbol == "AAPL"]) == 1


def test_upsert_articles_unknown_ticker_symbol_silently_skipped(
    db_session: Session, seeded_tickers: list
) -> None:
    repo.upsert_articles(
        db_session,
        [
            {
                "url": "https://example.com/goog-article",
                "title": "GOOG article",
                "summary": None,
                "source": None,
                "published_at": None,
                "ticker_symbols": ["GOOG"],
            }
        ],
    )
    article = repo.get_article_by_url(db_session, "https://example.com/goog-article")
    assert article is not None
    assert article.tickers == []


def test_upsert_articles_empty_list_is_noop(db_session: Session) -> None:
    repo.upsert_articles(db_session, [])
    assert db_session.query(Article).count() == 0


def test_upsert_articles_multiple_articles_in_one_call(
    db_session: Session, seeded_tickers: list
) -> None:
    articles_data = [
        {
            "url": "https://example.com/a1",
            "title": "A1",
            "summary": None,
            "source": None,
            "published_at": None,
            "ticker_symbols": ["AAPL"],
        },
        {
            "url": "https://example.com/a2",
            "title": "A2",
            "summary": None,
            "source": None,
            "published_at": None,
            "ticker_symbols": ["MSFT"],
        },
    ]
    repo.upsert_articles(db_session, articles_data)
    assert db_session.query(Article).count() == 2


# --- _poll_news scheduler tests ---


def test_poll_news_calls_upsert_when_tickers_exist(
    db_session: Session, seeded_tickers: list
) -> None:
    from app.scheduler import _poll_news

    fake_articles = [
        {
            "url": "https://x.com/1",
            "title": "T",
            "summary": None,
            "source": None,
            "published_at": None,
            "ticker_symbols": ["AAPL"],
        }
    ]
    with (
        patch("app.scheduler.SessionLocal", return_value=db_session),
        patch("app.scheduler.fetch_news", return_value=fake_articles) as mock_fetch,
        patch("app.scheduler.repo.upsert_articles") as mock_upsert,
    ):
        _poll_news()

    symbols = mock_fetch.call_args[0][0]
    assert set(symbols) == {"AAPL", "MSFT"}
    mock_upsert.assert_called_once_with(db_session, fake_articles)


def test_poll_news_skips_fetch_when_no_tickers(db_session: Session) -> None:
    from app.scheduler import _poll_news

    with (
        patch("app.scheduler.SessionLocal", return_value=db_session),
        patch("app.scheduler.fetch_news") as mock_fetch,
    ):
        _poll_news()

    mock_fetch.assert_not_called()


def test_poll_news_does_not_call_upsert_when_fetch_returns_empty(
    db_session: Session, seeded_tickers: list
) -> None:
    from app.scheduler import _poll_news

    with (
        patch("app.scheduler.SessionLocal", return_value=db_session),
        patch("app.scheduler.fetch_news", return_value=[]),
        patch("app.scheduler.repo.upsert_articles") as mock_upsert,
    ):
        _poll_news()

    mock_upsert.assert_not_called()


@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "GOOG"])
def test_get_ticker_news_parametrized_404_for_unknown(client: TestClient, symbol: str) -> None:
    response = client.get(f"/tickers/{symbol}/news")
    assert response.status_code == 404
