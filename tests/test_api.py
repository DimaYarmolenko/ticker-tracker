import pytest

import app.repository as repo
from app.auth import hash_password

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
        ("msft", "MSFT"),  # lowercase → uppercased
        ("  goog  ", "GOOG"),  # whitespace stripped + uppercased
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
def test_delete_existing_ticker(client, symbol):
    """Subscribing then unsubscribing removes the ticker from the user's list."""
    client.post("/tickers", json={"symbol": symbol})

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
def test_delete_ticker_case_insensitive(client, stored_symbol, delete_path):
    """DELETE normalises the path param to uppercase before lookup."""
    client.post("/tickers", json={"symbol": stored_symbol})

    response = client.delete(f"/tickers/{delete_path}")
    assert response.status_code == 204


@pytest.mark.parametrize("symbol", ["UNKNOWN", "FAKE", "XYZ"])
def test_delete_ticker_not_found(client, symbol):
    """Deleting a symbol that was never added must return 404."""
    response = client.delete(f"/tickers/{symbol}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


def test_user_cannot_see_another_users_tickers(client, db_session):
    """User A's subscriptions stay hidden from user B even though tickers are global."""
    client.post("/tickers", json={"symbol": "AAPL"})

    other = repo.create_user(db_session, "other@example.com", hash_password("super-secret"))
    client.cookies.clear()
    client.post(
        "/login",
        data={"email": "other@example.com", "password": "super-secret"},
        follow_redirects=False,
    )

    assert client.get("/tickers").json() == []
    assert client.delete("/tickers/AAPL").status_code == 404
    assert client.get("/tickers/AAPL/news").status_code == 404
    assert client.get("/tickers/AAPL/prices").status_code == 404
    # The global ticker row still exists in the DB.
    assert repo.get_by_symbol(db_session, "AAPL") is not None
    # Quiet pyright/lint: `other` is used to seed the DB row for the login call.
    assert other.email == "other@example.com"


def test_resubscribing_after_unsubscribe_reattaches_data(client):
    """After a user removes a ticker, re-adding it surfaces existing data again."""
    client.post("/tickers", json={"symbol": "AAPL"})
    client.delete("/tickers/AAPL")
    response = client.post("/tickers", json={"symbol": "AAPL"})
    assert response.status_code == 201
    listing = client.get("/tickers").json()
    assert any(t["symbol"] == "AAPL" for t in listing)
