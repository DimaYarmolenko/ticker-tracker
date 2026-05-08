from unittest.mock import MagicMock, patch

from app.price_fetcher import fetch_prices


def _make_fast_info(
    last_price=175.50,
    day_open=174.00,
    day_high=176.00,
    day_low=173.50,
    last_volume=55_000_000,
):
    info = MagicMock()
    info.last_price = last_price
    info.open = day_open
    info.day_high = day_high
    info.day_low = day_low
    info.last_volume = last_volume
    return info


def _make_tickers_mock(symbol_to_info: dict):
    tickers_mock = MagicMock()
    for symbol, info in symbol_to_info.items():
        tickers_mock.tickers[symbol].fast_info = info
    return tickers_mock


@patch("app.price_fetcher.yf.Tickers")
def test_empty_symbols_returns_empty(mock_tickers):
    result = fetch_prices([])
    assert result == []
    mock_tickers.assert_not_called()


@patch("app.price_fetcher.yf.Tickers")
def test_returns_price_data_for_valid_symbol(mock_tickers):
    mock_tickers.return_value = _make_tickers_mock({"AAPL": _make_fast_info()})
    result = fetch_prices(["AAPL"])
    assert len(result) == 1
    assert "symbol" in result[0]
    assert result[0]["symbol"] == "AAPL"
    assert result[0]["price"] == 175.50
    assert result[0]["open"] == 174.00
    assert result[0]["high"] == 176.00
    assert result[0]["low"] == 173.50
    assert result[0]["volume"] == 55_000_000


@patch("app.price_fetcher.yf.Tickers")
def test_skips_none_price(mock_tickers):
    mock_tickers.return_value = _make_tickers_mock({"AAPL": _make_fast_info(last_price=None)})
    result = fetch_prices(["AAPL"])
    assert result == []


@patch("app.price_fetcher.yf.Tickers")
def test_skips_nan_price(mock_tickers):
    mock_tickers.return_value = _make_tickers_mock(
        {"AAPL": _make_fast_info(last_price=float("nan"))}
    )
    result = fetch_prices(["AAPL"])
    assert result == []


@patch("app.price_fetcher.yf.Tickers")
def test_optional_fields_none_when_nan(mock_tickers):
    mock_tickers.return_value = _make_tickers_mock(
        {"AAPL": _make_fast_info(day_open=float("nan"), day_high=float("nan"))}
    )
    result = fetch_prices(["AAPL"])
    assert len(result) == 1
    assert result[0]["open"] is None
    assert result[0]["high"] is None


@patch("app.price_fetcher.yf.Tickers")
def test_continues_after_one_symbol_exception(mock_tickers):
    from unittest.mock import PropertyMock

    aapl_mock = MagicMock()
    aapl_mock.fast_info = _make_fast_info()
    msft_mock = MagicMock()
    type(msft_mock).fast_info = PropertyMock(side_effect=RuntimeError("boom"))

    tickers_mock = MagicMock()
    tickers_mock.tickers = {"AAPL": aapl_mock, "MSFT": msft_mock}
    mock_tickers.return_value = tickers_mock
    result = fetch_prices(["AAPL", "MSFT"])
    assert len(result) == 1
    assert result[0]["symbol"] == "AAPL"


@patch("app.price_fetcher.yf.Tickers")
def test_all_symbols_fail_returns_empty(mock_tickers):
    tickers_mock = MagicMock()
    type(tickers_mock.tickers["AAPL"]).fast_info = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    mock_tickers.return_value = tickers_mock
    result = fetch_prices(["AAPL"])
    assert result == []


@patch("app.price_fetcher.yf.Tickers")
def test_passes_all_symbols_to_yf_tickers(mock_tickers):
    info = _make_fast_info()
    tickers_mock = MagicMock()
    tickers_mock.tickers["AAPL"].fast_info = info
    tickers_mock.tickers["MSFT"].fast_info = info
    mock_tickers.return_value = tickers_mock
    fetch_prices(["AAPL", "MSFT"])
    mock_tickers.assert_called_once_with("AAPL MSFT")
