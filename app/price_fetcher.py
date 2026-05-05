import logging
import math

import yfinance as yf

from app.repository import PriceData

logger = logging.getLogger(__name__)


def fetch_prices(symbols: list[str]) -> list[PriceData]:
    if not symbols:
        return []
    results: list[PriceData] = []
    tickers = yf.Tickers(" ".join(symbols))
    for symbol in symbols:
        try:
            info = tickers.tickers[symbol].fast_info
            price = info.last_price
            if price is None or (isinstance(price, float) and math.isnan(price)):
                logger.warning("No price data for %s; skipping", symbol)
                continue
            results.append(
                PriceData(
                    symbol=symbol,
                    price=float(price),
                    open=_safe_float(info.open),
                    high=_safe_float(info.day_high),
                    low=_safe_float(info.day_low),
                    volume=_safe_int(info.last_volume),
                )
            )
        except Exception:
            logger.warning("Failed to fetch price for %s", symbol, exc_info=True)
    return results


def _safe_float(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    try:
        f = float(value)  # type: ignore[arg-type]
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None
