from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.repository as repo
from app.models import Price, Ticker
from app.repository import PriceData
from app.scheduler import _poll_prices


class TestGetTickerPricesEndpoint:
    def test_returns_prices_for_ticker(self, client: TestClient, seeded_prices: None) -> None:
        response = client.get("/tickers/AAPL/prices")
        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert len(response.json()["prices"]) == 2

    def test_returns_only_linked_prices(self, client: TestClient, seeded_prices: None) -> None:
        response = client.get("/tickers/MSFT/prices")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_response_shape(self, client: TestClient, seeded_prices: None) -> None:
        response = client.get("/tickers/AAPL/prices")
        body = response.json()
        assert set(body.keys()) == {"ticker", "total", "limit", "offset", "prices"}
        assert body["ticker"] == "AAPL"
        price = body["prices"][0]
        assert set(price.keys()) == {"id", "price", "open", "high", "low", "volume", "fetched_at"}

    def test_pagination_limit(self, client: TestClient, seeded_prices: None) -> None:
        response = client.get("/tickers/AAPL/prices?limit=1")
        body = response.json()
        assert len(body["prices"]) == 1
        assert body["total"] == 2
        assert body["limit"] == 1

    def test_pagination_offset(self, client: TestClient, seeded_prices: None) -> None:
        r1 = client.get("/tickers/AAPL/prices?limit=1&offset=0")
        r2 = client.get("/tickers/AAPL/prices?limit=1&offset=1")
        ids1 = [p["id"] for p in r1.json()["prices"]]
        ids2 = [p["id"] for p in r2.json()["prices"]]
        assert ids1 != ids2

    def test_offset_beyond_total_returns_empty_list(
        self, client: TestClient, seeded_prices: None
    ) -> None:
        response = client.get("/tickers/AAPL/prices?offset=999")
        assert response.status_code == 200
        assert response.json()["prices"] == []

    def test_symbol_case_insensitive(self, client: TestClient, seeded_prices: None) -> None:
        response = client.get("/tickers/aapl/prices")
        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"

    def test_empty_when_no_prices(self, client: TestClient, seeded_tickers: list[Ticker]) -> None:
        response = client.get("/tickers/AAPL/prices")
        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert response.json()["prices"] == []

    def test_unknown_symbol_returns_404(self, client: TestClient) -> None:
        response = client.get("/tickers/UNKNOWN/prices")
        assert response.status_code == 404

    def test_404_has_detail_field(self, client: TestClient) -> None:
        response = client.get("/tickers/UNKNOWN/prices")
        assert "detail" in response.json()

    def test_newest_first_ordering(self, client: TestClient, seeded_prices: None) -> None:
        response = client.get("/tickers/AAPL/prices")
        timestamps = [p["fetched_at"] for p in response.json()["prices"]]
        assert timestamps == sorted(timestamps, reverse=True)


class TestInsertPricesRepository:
    def test_insert_prices_creates_rows(
        self, db_session: Session, seeded_tickers: list[Ticker]
    ) -> None:
        repo.insert_prices(
            db_session,
            [PriceData(symbol="AAPL", price=100.0, open=99.0, high=101.0, low=98.0, volume=1000)],
        )
        prices = db_session.query(Price).all()
        assert len(prices) == 1
        assert prices[0].price == 100.0

    def test_insert_prices_skips_unknown_symbol(self, db_session: Session) -> None:
        repo.insert_prices(
            db_session,
            [PriceData(symbol="GOOG", price=100.0, open=None, high=None, low=None, volume=None)],
        )
        assert db_session.query(Price).count() == 0

    def test_insert_prices_empty_list_is_noop(
        self, db_session: Session, seeded_tickers: list[Ticker]
    ) -> None:
        repo.insert_prices(db_session, [])
        assert db_session.query(Price).count() == 0

    def test_insert_prices_optional_fields_stored_as_none(
        self, db_session: Session, seeded_tickers: list[Ticker]
    ) -> None:
        repo.insert_prices(
            db_session,
            [PriceData(symbol="AAPL", price=100.0, open=None, high=None, low=None, volume=None)],
        )
        price = db_session.query(Price).first()
        assert price is not None
        assert price.open is None
        assert price.volume is None

    def test_insert_prices_multiple_symbols(
        self, db_session: Session, seeded_tickers: list[Ticker]
    ) -> None:
        repo.insert_prices(
            db_session,
            [
                PriceData(symbol="AAPL", price=100.0, open=None, high=None, low=None, volume=None),
                PriceData(symbol="MSFT", price=200.0, open=None, high=None, low=None, volume=None),
            ],
        )
        assert db_session.query(Price).count() == 2

    def test_delete_ticker_cascades_to_prices(
        self, db_session: Session, seeded_tickers: list[Ticker]
    ) -> None:
        repo.insert_prices(
            db_session,
            [PriceData(symbol="AAPL", price=100.0, open=None, high=None, low=None, volume=None)],
        )
        assert db_session.query(Price).count() == 1
        ticker = repo.get_by_symbol(db_session, "AAPL")
        repo.delete(db_session, ticker)
        assert db_session.query(Price).count() == 0


class TestPollPricesScheduler:
    def test_poll_prices_calls_insert_when_tickers_exist(self) -> None:
        mock_ticker = MagicMock()
        mock_ticker.symbol = "AAPL"
        mock_price = PriceData(
            symbol="AAPL", price=100.0, open=None, high=None, low=None, volume=None
        )

        with (
            patch("app.database.SessionLocal") as mock_session_local,
            patch("app.scheduler.repo.get_all", return_value=[mock_ticker]),
            patch("app.scheduler.fetch_prices", return_value=[mock_price]) as mock_fetch,
            patch("app.scheduler.repo.insert_prices") as mock_insert,
        ):
            mock_session_local.return_value = MagicMock()
            _poll_prices()
            mock_fetch.assert_called_once_with(["AAPL"])
            mock_insert.assert_called_once()

    def test_poll_prices_skips_when_no_tickers(self) -> None:
        with (
            patch("app.database.SessionLocal") as mock_session_local,
            patch("app.scheduler.repo.get_all", return_value=[]),
            patch("app.scheduler.fetch_prices") as mock_fetch,
        ):
            mock_session_local.return_value = MagicMock()
            _poll_prices()
            mock_fetch.assert_not_called()

    def test_poll_prices_no_insert_when_fetch_returns_empty(self) -> None:
        mock_ticker = MagicMock()
        mock_ticker.symbol = "AAPL"

        with (
            patch("app.database.SessionLocal") as mock_session_local,
            patch("app.scheduler.repo.get_all", return_value=[mock_ticker]),
            patch("app.scheduler.fetch_prices", return_value=[]),
            patch("app.scheduler.repo.insert_prices") as mock_insert,
        ):
            mock_session_local.return_value = MagicMock()
            _poll_prices()
            mock_insert.assert_not_called()
