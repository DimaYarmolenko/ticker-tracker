from datetime import datetime, timedelta, timezone
from email.utils import format_datetime as _fmt_rfc2822
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.news_fetcher import _parse_entry, fetch_news

_NOW = datetime.now(timezone.utc)
_RECENT_PUB_DATE = _fmt_rfc2822(_NOW - timedelta(hours=1))
_OLD_PUB_DATE = _fmt_rfc2822(_NOW - timedelta(days=10))
_FIVE_DAYS_AGO_PUB_DATE = _fmt_rfc2822(_NOW - timedelta(days=5))


def _make_rss_xml(entries: list[dict]) -> str:
    items = ""
    for e in entries:
        items += f"""<item>
            <title>{e.get("title", "")}</title>
            <link>{e.get("link", "")}</link>
            <description>{e.get("summary", "")}</description>
            <source url="">{e.get("source_title", "TestSource")}</source>
            <pubDate>{e.get("pub_date", _RECENT_PUB_DATE)}</pubDate>
        </item>"""
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'


def _make_mock_response(xml_text: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.text = xml_text
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# --- _parse_entry tests ---


def test_parse_entry_full_entry() -> None:
    entry = {
        "link": "https://example.com/article",
        "title": "AAPL surges",
        "summary": "Apple stock up 5%",
        "source": {"title": "Reuters"},
        "published_parsed": (2026, 4, 28, 10, 0, 0, 0, 0, 0),
    }
    url, title, summary, source, published_at = _parse_entry(entry)
    assert url == "https://example.com/article"
    assert title == "AAPL surges"
    assert summary == "Apple stock up 5%"
    assert source == "Reuters"
    assert published_at == datetime(2026, 4, 28, 10, 0, 0, tzinfo=timezone.utc)


def test_parse_entry_missing_optional_fields() -> None:
    entry = {"link": "https://example.com/x", "title": "Bare entry"}
    url, title, summary, source, published_at = _parse_entry(entry)
    assert url == "https://example.com/x"
    assert title == "Bare entry"
    assert summary is None
    assert source is None
    assert published_at is None


def test_parse_entry_empty_summary_becomes_none() -> None:
    entry = {"link": "https://example.com/x", "title": "T", "summary": ""}
    _, _, summary, _, _ = _parse_entry(entry)
    assert summary is None


def test_parse_entry_source_with_no_title_becomes_none() -> None:
    entry = {"link": "https://x.com", "title": "T", "source": {"url": "https://x.com"}}
    _, _, _, source, _ = _parse_entry(entry)
    assert source is None


# --- fetch_news tests ---


def test_fetch_news_empty_symbols_returns_empty() -> None:
    with patch("app.news_fetcher.httpx.get") as mock_get:
        result = fetch_news([])
    assert result == []
    mock_get.assert_not_called()


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_returns_article_for_single_symbol(mock_get: MagicMock) -> None:
    xml = _make_rss_xml(
        [
            {
                "title": "AAPL hits new high",
                "link": "https://example.com/aapl-1",
                "summary": "Apple stock surges",
                "source_title": "Reuters",
            }
        ]
    )
    mock_get.return_value = _make_mock_response(xml)

    result = fetch_news(["AAPL"])

    assert len(result) == 1
    article = result[0]
    assert article["url"] == "https://example.com/aapl-1"
    assert article["title"] == "AAPL hits new high"
    assert article["summary"] == "Apple stock surges"
    assert article["source"] == "Reuters"
    assert "AAPL" in article["ticker_symbols"]
    assert isinstance(article["published_at"], datetime)


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_skips_entry_with_missing_url(mock_get: MagicMock) -> None:
    xml = _make_rss_xml([{"title": "Some title", "link": ""}])
    mock_get.return_value = _make_mock_response(xml)
    assert fetch_news(["AAPL"]) == []


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_skips_entry_with_missing_title(mock_get: MagicMock) -> None:
    xml = _make_rss_xml([{"title": "", "link": "https://example.com/article"}])
    mock_get.return_value = _make_mock_response(xml)
    assert fetch_news(["AAPL"]) == []


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_skips_entry_older_than_cutoff(
    mock_get: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEWS_MAX_AGE_DAYS", "2")
    xml = _make_rss_xml(
        [{"title": "Old news", "link": "https://example.com/old", "pub_date": _OLD_PUB_DATE}]
    )
    mock_get.return_value = _make_mock_response(xml)
    assert fetch_news(["AAPL"]) == []


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_includes_entry_with_no_published_date(mock_get: MagicMock) -> None:
    xml = '<?xml version="1.0"?><rss version="2.0"><channel><item><title>Undated</title><link>https://example.com/undated</link></item></channel></rss>'
    mock_get.return_value = _make_mock_response(xml)
    result = fetch_news(["AAPL"])
    assert len(result) == 1
    assert result[0]["published_at"] is None


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_deduplicates_same_url_across_symbols(mock_get: MagicMock) -> None:
    xml = _make_rss_xml([{"title": "Tech giants rally", "link": "https://example.com/shared"}])
    mock_get.return_value = _make_mock_response(xml)

    result = fetch_news(["AAPL", "MSFT"])

    assert len(result) == 1
    assert set(result[0]["ticker_symbols"]) == {"AAPL", "MSFT"}
    assert mock_get.call_count == 2


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_cross_mention_adds_symbol_to_ticker_symbols(mock_get: MagicMock) -> None:
    aapl_xml = _make_rss_xml(
        [{"title": "AAPL and MSFT lead tech rally", "link": "https://example.com/article-1"}]
    )
    msft_xml = _make_rss_xml(
        [{"title": "MSFT earnings beat", "link": "https://example.com/article-2"}]
    )
    mock_get.side_effect = [_make_mock_response(aapl_xml), _make_mock_response(msft_xml)]

    result = fetch_news(["AAPL", "MSFT"])

    article_1 = next(a for a in result if a["url"] == "https://example.com/article-1")
    assert "AAPL" in article_1["ticker_symbols"]
    assert "MSFT" in article_1["ticker_symbols"]


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_cross_mention_does_not_duplicate_existing_symbol(mock_get: MagicMock) -> None:
    xml = _make_rss_xml(
        [{"title": "AAPL reaches all time high", "link": "https://example.com/aapl-ath"}]
    )
    mock_get.return_value = _make_mock_response(xml)

    result = fetch_news(["AAPL"])
    assert result[0]["ticker_symbols"].count("AAPL") == 1


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_network_error_for_one_symbol_continues(mock_get: MagicMock) -> None:
    xml = _make_rss_xml([{"title": "MSFT earnings beat", "link": "https://example.com/msft-1"}])
    mock_get.side_effect = [
        httpx.HTTPError("connection refused"),
        _make_mock_response(xml),
    ]

    result = fetch_news(["AAPL", "MSFT"])

    assert len(result) == 1
    assert result[0]["url"] == "https://example.com/msft-1"
    assert "MSFT" in result[0]["ticker_symbols"]


@patch("app.news_fetcher.httpx.get")
def test_fetch_news_all_symbols_fail_returns_empty(mock_get: MagicMock) -> None:
    mock_get.side_effect = httpx.HTTPError("timeout")
    assert fetch_news(["AAPL", "MSFT"]) == []


@pytest.mark.parametrize("max_age_days,expected_count", [("7", 1), ("1", 0)])
@patch("app.news_fetcher.httpx.get")
def test_fetch_news_respects_news_max_age_days_env_var(
    mock_get: MagicMock,
    max_age_days: str,
    expected_count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEWS_MAX_AGE_DAYS", max_age_days)
    xml = _make_rss_xml(
        [
            {
                "title": "AAPL article 5 days old",
                "link": "https://example.com/aapl-old",
                "pub_date": _FIVE_DAYS_AGO_PUB_DATE,
            }
        ]
    )
    mock_get.return_value = _make_mock_response(xml)
    result = fetch_news(["AAPL"])
    assert len(result) == expected_count
