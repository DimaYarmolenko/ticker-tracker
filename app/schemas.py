import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models import ImpactLabel

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,20}$")


class ArticleResponse(BaseModel):
    id: str
    url: str
    title: str
    summary: str | None
    source: str | None
    published_at: datetime | None
    fetched_at: datetime
    importance: int | None = None
    evaluated_at: datetime | None = None
    impact: ImpactLabel | None = None
    impact_confidence: float | None = None

    model_config = {"from_attributes": True}


class ArticleListResponse(BaseModel):
    ticker: str
    total: int
    limit: int
    offset: int
    articles: list[ArticleResponse]


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PriceBase(BaseModel):
    price: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None


class PriceResponse(PriceBase):
    id: str
    fetched_at: datetime

    model_config = {"from_attributes": True}


class PriceListResponse(BaseModel):
    ticker: str
    total: int
    limit: int
    offset: int
    prices: list[PriceResponse]


class TickerCreate(BaseModel):
    symbol: str

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        normalized = v.strip().upper()
        if not normalized:
            raise ValueError("Symbol is required")
        if not _SYMBOL_PATTERN.match(normalized):
            raise ValueError("Symbol must be 1-20 chars: A-Z, 0-9, '.', '-'")
        return normalized


class TickerResponse(BaseModel):
    id: str
    symbol: str
    date_added: datetime

    model_config = {"from_attributes": True}
