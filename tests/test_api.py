import pytest


# ---------------------------------------------------------------------------
# GET /tickers
# ---------------------------------------------------------------------------


def test_list_tickers_empty(client):
    response = client.get("/tickers")
    assert response.status_code == 200
    assert response.json() == []


def test_list_tickers_returns_seeded_data(client, seeded_tickers):
    """Verify list endpoint returns all pre-seeded tickers."""
    response = client.get("/tickers")
    assert response.status_code == 200
    symbols = {t["symbol"] for t in response.json()}
    assert symbols == {t.symbol for t in seeded_tickers}


# ---------------------------------------------------------------------------
# POST /tickers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "symbol, expected_symbol",
    [
        ("AAPL", "AAPL"),
        ("msft", "MSFT"),          # lowercase → uppercased
        ("  goog  ", "GOOG"),      # whitespace stripped + uppercased
        ("TSLA", "TSLA"),
        ("BRK.B", "BRK.B"),
    ],
)
def test_add_ticker_normalizes_symbol(client, symbol, expected_symbol):
    response = client.post("/tickers", json={"symbol": symbol})
    assert response.status_code == 201
    body = response.json()
    assert body["symbol"] == expected_symbol
    assert "id" in body
    assert "date_added" in body


@pytest.mark.parametrize("symbol", ["AAPL", "NVDA", "SPY"])
def test_add_ticker_conflict(client, symbol):
    """Second POST with the same symbol must return 409."""
    client.post("/tickers", json={"symbol": symbol})
    response = client.post("/tickers", json={"symbol": symbol})
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# DELETE /tickers/{symbol}
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol", ["AAPL", "MSFT", "GOOG"])
def test_delete_existing_ticker(client, db_session, symbol):
    """Ticker created via fixture is deleted and no longer appears in list."""
    import app.repository as repo
    repo.create(db_session, symbol)

    response = client.delete(f"/tickers/{symbol}")
    assert response.status_code == 204

    tickers = client.get("/tickers").json()
    assert all(t["symbol"] != symbol for t in tickers)


@pytest.mark.parametrize(
    "stored_symbol, delete_path",
    [
        ("AAPL", "aapl"),
        ("MSFT", "Msft"),
        ("GOOG", "goog"),
    ],
)
def test_delete_ticker_case_insensitive(client, db_session, stored_symbol, delete_path):
    """DELETE normalises the path param to uppercase before lookup."""
    import app.repository as repo
    repo.create(db_session, stored_symbol)

    response = client.delete(f"/tickers/{delete_path}")
    assert response.status_code == 204


@pytest.mark.parametrize("symbol", ["UNKNOWN", "FAKE", "XYZ"])
def test_delete_ticker_not_found(client, symbol):
    """Deleting a symbol that was never added must return 404."""
    response = client.delete(f"/tickers/{symbol}")
    assert response.status_code == 404
