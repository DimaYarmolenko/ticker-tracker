import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

article_tickers = Table(
    "article_tickers",
    Base.metadata,
    Column("article_id", String(36), ForeignKey("articles.id"), primary_key=True),
    Column("ticker_id", String(36), ForeignKey("tickers.id"), primary_key=True),
)


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    date_added: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article", secondary=article_tickers, back_populates="tickers"
    )


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    tickers: Mapped[list["Ticker"]] = relationship(
        "Ticker", secondary=article_tickers, back_populates="articles"
    )
