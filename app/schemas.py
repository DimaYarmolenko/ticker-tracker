from datetime import datetime

from pydantic import BaseModel, field_validator


class ArticleResponse(BaseModel):
    id: str
    url: str
    title: str
    summary: str | None
    source: str | None
    published_at: datetime | None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class ArticleListResponse(BaseModel):
    ticker: str
    total: int
    limit: int
    offset: int
    articles: list[ArticleResponse]


class TickerCreate(BaseModel):
    symbol: str

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()


class TickerResponse(BaseModel):
    id: str
    symbol: str
    date_added: datetime

    model_config = {"from_attributes": True}
