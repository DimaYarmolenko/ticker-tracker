from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

import app.repository as repo
from app.database import get_db
from app.schemas import TickerCreate

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _render_tickers(
    request: Request, db: Session, *, error: str | None = None, selected: str | None = None
) -> HTMLResponse:
    tickers = repo.get_all(db)
    return templates.TemplateResponse(
        request,
        "_tickers.html",
        {"tickers": tickers, "selected": selected, "error": error},
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    tickers = repo.get_all(db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tickers": tickers, "selected": None, "error": None},
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
    error: str | None = None
    try:
        payload = TickerCreate(symbol=symbol)
    except ValidationError:
        return _render_tickers(request, db, error="Invalid symbol")

    if not payload.symbol:
        error = "Symbol is required"
    elif repo.get_by_symbol(db, payload.symbol):
        error = f"{payload.symbol} is already tracked"
    else:
        repo.create(db, payload.symbol)

    return _render_tickers(request, db, error=error, selected=payload.symbol)


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
        return HTMLResponse(
            f'<section id="articles" class="articles"><p class="empty">'
            f"{upper} not found</p></section>",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    rows, total = repo.get_articles_page(db, ticker.id, limit=limit, offset=offset)
    articles = [
        {
            "title": article.title,
            "url": article.url,
            "source": article.source,
            "published_at": article.published_at,
            "importance": article.importance,
            "impact": link.impact,
            "impact_confidence": link.impact_confidence,
        }
        for article, link in rows
    ]
    return templates.TemplateResponse(
        request,
        "_articles.html",
        {
            "ticker": upper,
            "articles": articles,
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + len(articles) < total,
            "next_offset": offset + limit,
            "is_initial": offset == 0,
        },
    )
