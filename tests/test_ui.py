import json
import re


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Ticker Tracker" in response.text
    assert "Select a ticker" in response.text


def test_get_ui_tickers_partial(client, seeded_tickers):
    response = client.get("/ui/tickers")
    assert response.status_code == 200
    assert "AAPL" in response.text
    assert "MSFT" in response.text


def test_add_ticker_via_ui_normalizes_symbol(client):
    response = client.post("/ui/tickers", data={"symbol": "aapl"})
    assert response.status_code == 200
    assert "AAPL" in response.text
    listing = client.get("/tickers").json()
    assert {t["symbol"] for t in listing} == {"AAPL"}


def test_add_ticker_duplicate_shows_inline_error(client):
    client.post("/ui/tickers", data={"symbol": "AAPL"})
    response = client.post("/ui/tickers", data={"symbol": "AAPL"})
    assert response.status_code == 200
    assert "already tracked" in response.text
    listing = client.get("/tickers").json()
    assert len([t for t in listing if t["symbol"] == "AAPL"]) == 1


def test_add_ticker_preserves_input_value_on_duplicate(client):
    """Bug #1: input value must survive a failed (duplicate) add so the user can edit."""
    client.post("/ui/tickers", data={"symbol": "AAPL"})
    response = client.post("/ui/tickers", data={"symbol": "AAPL"})
    assert response.status_code == 200
    assert 'value="AAPL"' in response.text


def test_add_ticker_clears_input_value_on_success(client):
    """Successful add must leave the input empty so the user can type the next symbol."""
    response = client.post("/ui/tickers", data={"symbol": "AAPL"})
    assert response.status_code == 200
    assert 'value="AAPL"' not in response.text


def test_add_ticker_no_selection_on_duplicate(client):
    """Bug #2: a failed (duplicate) add must not highlight any sidebar row as selected."""
    client.post("/ui/tickers", data={"symbol": "AAPL"})
    response = client.post("/ui/tickers", data={"symbol": "AAPL"})
    assert response.status_code == 200
    assert "ticker-row is-selected" not in response.text


def test_add_ticker_sets_selection_on_success(client):
    """Successful add highlights the new ticker as selected."""
    response = client.post("/ui/tickers", data={"symbol": "AAPL"})
    assert response.status_code == 200
    assert "ticker-row is-selected" in response.text


def test_add_ticker_empty_symbol_shows_error(client):
    """Whitespace-only symbols strip to empty and must surface a 'required' error."""
    response = client.post("/ui/tickers", data={"symbol": "   "})
    assert response.status_code == 200
    assert "Symbol is required" in response.text
    listing = client.get("/tickers").json()
    assert listing == []


def test_add_ticker_invalid_charset_shows_error(client):
    """Symbols with disallowed characters surface an inline charset error and are not stored."""
    response = client.post("/ui/tickers", data={"symbol": "A!B"})
    assert response.status_code == 200
    assert "Symbol must be 1-20 chars" in response.text
    listing = client.get("/tickers").json()
    assert listing == []


def test_json_add_ticker_invalid_charset_returns_422(client):
    """JSON API rejects disallowed characters with a 422 from pydantic validation."""
    response = client.post("/tickers", json={"symbol": "A!B"})
    assert response.status_code == 422


def test_delete_ticker_via_ui_removes_row(client, seeded_tickers):
    response = client.delete("/ui/tickers/AAPL")
    assert response.status_code == 200
    assert "AAPL" not in response.text
    assert "MSFT" in response.text


def test_delete_unknown_ticker_returns_error_partial(client):
    response = client.delete("/ui/tickers/UNKNOWN")
    assert response.status_code == 200
    assert "not found" in response.text


def test_get_articles_renders_titles(client, seeded_articles):
    response = client.get("/ui/tickers/AAPL/articles")
    assert response.status_code == 200
    assert "AAPL hits new high" in response.text
    assert "Tech giants rally" in response.text
    assert "Load more" not in response.text


def test_get_articles_unknown_ticker_returns_404(client):
    response = client.get("/ui/tickers/UNKNOWN/articles")
    assert response.status_code == 404
    assert "UNKNOWN not found" in response.text


def test_get_articles_404_escapes_symbol(client):
    """Bug #4: the 404 branch must not interpolate raw HTML from the URL path."""
    response = client.get("/ui/tickers/<svg>/articles")
    assert response.status_code == 404
    assert "<SVG>" not in response.text
    assert "<svg>" not in response.text
    assert "&lt;SVG&gt;" in response.text


def test_get_articles_empty_for_known_ticker(client, seeded_tickers):
    response = client.get("/ui/tickers/AAPL/articles")
    assert response.status_code == 200
    assert "No articles yet" in response.text


def test_get_articles_load_more_appears_when_total_exceeds_limit(client, seeded_articles):
    response = client.get("/ui/tickers/AAPL/articles?limit=1")
    assert response.status_code == 200
    assert "Load more" in response.text
    assert "offset=1" in response.text


def test_get_articles_partial_swap_omits_header(client, seeded_articles):
    response = client.get("/ui/tickers/AAPL/articles?limit=1&offset=1")
    assert response.status_code == 200
    assert '<section id="articles"' not in response.text
    assert "Tech giants rally" in response.text or "AAPL hits new high" in response.text


def _extract_chart_points(body: str, symbol: str) -> list[dict]:
    match = re.search(
        rf'<script type="application/json" id="chart-data-{symbol}">(.*?)</script>',
        body,
        re.DOTALL,
    )
    assert match, f"chart-data-{symbol} script not found"
    return json.loads(match.group(1))


def test_get_chart_renders_section_with_auto_refresh(client, seeded_tickers, seeded_prices):
    response = client.get("/ui/tickers/AAPL/chart")
    assert response.status_code == 200
    assert 'id="chart"' in response.text
    assert 'id="chart-canvas-AAPL"' in response.text
    assert re.search(r'hx-trigger="every \d+s\[!document\.hidden\]"', response.text), (
        "chart section must auto-refresh on an interval, paused when tab is hidden"
    )
    assert 'hx-get="/ui/tickers/AAPL/chart"' in response.text


def test_get_chart_embeds_points_in_ascending_order(client, seeded_tickers, seeded_prices):
    response = client.get("/ui/tickers/AAPL/chart")
    points = _extract_chart_points(response.text, "AAPL")
    assert [p["p"] for p in points] == [175.50, 176.20]
    timestamps = [p["t"] for p in points]
    assert timestamps == sorted(timestamps)


def test_get_chart_empty_state_when_no_prices(client, seeded_tickers):
    response = client.get("/ui/tickers/AAPL/chart")
    assert response.status_code == 200
    assert "No price data yet" in response.text
    assert 'id="chart-canvas-AAPL"' not in response.text


def test_get_chart_unknown_ticker_returns_404(client):
    response = client.get("/ui/tickers/UNKNOWN/chart")
    assert response.status_code == 404
    assert "UNKNOWN not found" in response.text


def test_get_view_contains_chart_and_articles(client, seeded_articles, seeded_prices):
    response = client.get("/ui/tickers/AAPL/view")
    assert response.status_code == 200
    assert 'id="chart"' in response.text
    assert 'id="articles"' in response.text
    assert "AAPL hits new high" in response.text
    assert 'id="chart-canvas-AAPL"' in response.text


def test_get_view_unknown_ticker_returns_404(client):
    response = client.get("/ui/tickers/UNKNOWN/view")
    assert response.status_code == 404
    assert "UNKNOWN not found" in response.text


def test_sidebar_button_targets_view_route(client, seeded_tickers):
    response = client.get("/ui/tickers")
    assert response.status_code == 200
    assert 'hx-get="/ui/tickers/AAPL/view"' in response.text
    assert 'hx-target="#main-pane"' in response.text
