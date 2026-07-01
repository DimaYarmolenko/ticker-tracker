import bisect
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, TypedDict

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

import app.repository as repo
from app.config import read_int_env
from app.database import get_db
from app.models import Article, ArticleTicker, ImpactLabel, Price
from app.schemas import TickerCreate

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


_ARTICLES_INITIAL_LIMIT = 20
_MIN_REFRESH_SECONDS = 60
_IMPORTANT_IMPORTANCE_THRESHOLD = 4


class ChartPoint(TypedDict):
    t: int
    p: float


class ChartMarker(TypedDict):
    t: int
    p: float
    impact: ImpactLabel
    importance: int
    confidence: float
    title: str
    source: str
    url: str


def _chart_refresh_seconds() -> int:
    minutes = read_int_env("PRICE_POLL_INTERVAL_MINUTES", required=False, default=30)
    return max(_MIN_REFRESH_SECONDS, minutes * 60)


def _to_epoch_ms(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _build_chart_markers(
    prices: list[Price], rows: list[tuple[Article, ArticleTicker]]
) -> list[ChartMarker]:
    if not prices or not rows:
        return []
    price_ms = [_to_epoch_ms(p.fetched_at) for p in prices]
    earliest_ms = price_ms[0]
    markers: list[ChartMarker] = []
    for article, link in rows:
        target_ms = _to_epoch_ms(article.published_at)
        if target_ms < earliest_ms:
            continue
        idx = bisect.bisect_left(price_ms, target_ms)
        if idx == 0:
            interp = prices[0].price
        elif idx >= len(prices):
            interp = prices[-1].price
        else:
            a_ms, b_ms = price_ms[idx - 1], price_ms[idx]
            a_p, b_p = prices[idx - 1].price, prices[idx].price
            interp = a_p if b_ms == a_ms else a_p + (target_ms - a_ms) / (b_ms - a_ms) * (b_p - a_p)
        markers.append(
            ChartMarker(
                t=target_ms,
                p=interp,
                impact=link.impact or ImpactLabel.NEUTRAL,
                importance=article.importance,
                confidence=link.impact_confidence if link.impact_confidence is not None else 1.0,
                title=article.title,
                source=article.source or "",
                url=article.url,
            )
        )
    return markers


def _build_chart_context(
    db: Session,
    ticker_id: str,
    ticker_symbol: str,
    prices: list[Price],
    refresh_seconds: int,
) -> dict:
    points: list[ChartPoint] = [ChartPoint(t=_to_epoch_ms(p.fetched_at), p=p.price) for p in prices]
    markers: list[ChartMarker] = []
    if prices:
        # Article.published_at is a naive DateTime column; normalize to naive UTC
        # so the repo's >= comparison stays on the same type.
        since = prices[0].fetched_at
        if since.tzinfo is not None:
            since = since.astimezone(timezone.utc).replace(tzinfo=None)
        evaluated = repo.get_evaluated_articles_for_chart(db, ticker_id, since=since)
        markers = _build_chart_markers(prices, evaluated)
    return {
        "ticker": ticker_symbol,
        "points": points,
        "markers": markers,
        "refresh_seconds": refresh_seconds,
    }


def _build_articles_context(
    ticker_symbol: str,
    rows: list[tuple[Article, ArticleTicker]],
    total: int,
    limit: int,
    offset: int,
) -> dict:
    articles = [
        {
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "published_at": article.published_at,
            "importance": article.importance,
            "is_important": article.importance is not None
            and article.importance >= _IMPORTANT_IMPORTANCE_THRESHOLD,
            "impact": link.impact,
            "impact_confidence": link.impact_confidence,
        }
        for article, link in rows
    ]
    return {
        "ticker": ticker_symbol,
        "articles": articles,
        "offset": offset,
        "limit": limit,
        "total": total,
        "has_more": offset + len(articles) < total,
        "next_offset": offset + limit,
        "is_initial": offset == 0,
    }


def _render_tickers(
    request: Request,
    db: Session,
    *,
    error: str | None = None,
    selected: str | None = None,
    form_value: str | None = None,
) -> HTMLResponse:
    tickers = repo.get_all(db)
    return templates.TemplateResponse(
        request,
        "_tickers.html",
        {
            "tickers": tickers,
            "selected": selected,
            "error": error,
            "form_value": form_value,
        },
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    tickers = repo.get_all(db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tickers": tickers, "selected": None, "error": None, "form_value": None},
    )


@router.get("/ui/tickers", response_class=HTMLResponse)
def ui_tickers(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return _render_tickers(request, db)


@router.post("/ui/tickers", response_class=HTMLResponse)
def ui_add_ticker(
    request: Request,
    symbol: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        payload = TickerCreate(symbol=symbol)
    except ValidationError as exc:
        msg = exc.errors()[0].get("msg", "Invalid symbol")
        # Pydantic v2 prefixes user messages with "Value error, "; trim it.
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        return _render_tickers(request, db, error=msg, form_value=symbol)

    if repo.get_by_symbol(db, payload.symbol):
        return _render_tickers(
            request,
            db,
            error=f"{payload.symbol} is already tracked",
            form_value=payload.symbol,
        )

    repo.create(db, payload.symbol)
    return _render_tickers(request, db, selected=payload.symbol)


@router.delete("/ui/tickers/{symbol}", response_class=HTMLResponse)
def ui_delete_ticker(request: Request, symbol: str, db: Session = Depends(get_db)) -> HTMLResponse:
    upper = symbol.upper()
    ticker = repo.get_by_symbol(db, upper)
    if not ticker:
        return _render_tickers(request, db, error=f"{upper} not found")
    repo.delete(db, ticker)
    return _render_tickers(request, db)


@router.get("/ui/tickers/{symbol}/articles", response_class=HTMLResponse)
def ui_ticker_articles(
    request: Request,
    symbol: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    upper = symbol.upper()
    ticker = repo.get_by_symbol(db, upper)
    if not ticker:
        return templates.TemplateResponse(
            request,
            "_articles_not_found.html",
            {"ticker": upper},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    rows, total = repo.get_articles_page(db, ticker.id, limit=limit, offset=offset)
    return templates.TemplateResponse(
        request,
        "_articles.html",
        _build_articles_context(upper, rows, total, limit=limit, offset=offset),
    )


@router.get("/ui/tickers/{symbol}/chart", response_class=HTMLResponse)
def ui_ticker_chart(
    request: Request,
    symbol: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    upper = symbol.upper()
    ticker = repo.get_by_symbol(db, upper)
    if not ticker:
        return templates.TemplateResponse(
            request,
            "_chart_not_found.html",
            {"ticker": upper},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    prices = repo.get_price_history(db, ticker.id, limit=repo.PRICE_HISTORY_LIMIT)
    return templates.TemplateResponse(
        request,
        "_chart.html",
        _build_chart_context(db, ticker.id, upper, prices, _chart_refresh_seconds()),
    )


@router.get("/ui/tickers/{symbol}/view", response_class=HTMLResponse)
def ui_ticker_view(
    request: Request,
    symbol: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    upper = symbol.upper()
    ticker = repo.get_by_symbol(db, upper)
    if not ticker:
        return templates.TemplateResponse(
            request,
            "_view_not_found.html",
            {"ticker": upper},
            status_code=status.HTTP_404_NOT_FOUND,
        )
    prices = repo.get_price_history(db, ticker.id, limit=repo.PRICE_HISTORY_LIMIT)
    rows, total = repo.get_articles_page(db, ticker.id, limit=_ARTICLES_INITIAL_LIMIT, offset=0)
    context = _build_chart_context(db, ticker.id, upper, prices, _chart_refresh_seconds()) | (
        _build_articles_context(upper, rows, total, limit=_ARTICLES_INITIAL_LIMIT, offset=0)
    )
    return templates.TemplateResponse(request, "_ticker_view.html", context)
