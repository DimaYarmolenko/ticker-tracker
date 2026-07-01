import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImpactLabel(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ArticleTicker(Base):
    __tablename__ = "article_tickers"

    article_id: Mapped[str] = mapped_column(String(36), ForeignKey("articles.id"), primary_key=True)
    ticker_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickers.id"), primary_key=True)
    impact: Mapped[ImpactLabel | None] = mapped_column(String(16))
    impact_confidence: Mapped[float | None] = mapped_column(Float)


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    date_added: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    articles: Mapped[list["Article"]] = relationship(
        "Article", secondary=ArticleTicker.__table__, back_populates="tickers"
    )
    prices: Mapped[list["Price"]] = relationship(
        "Price", back_populates="ticker", cascade="all, delete-orphan"
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
    importance: Mapped[int | None] = mapped_column(Integer)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime)
    evaluator_version: Mapped[str | None] = mapped_column(String(40))
    tickers: Mapped[list["Ticker"]] = relationship(
        "Ticker", secondary=ArticleTicker.__table__, back_populates="articles"
    )


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="prices")

    __table_args__ = (Index("ix_prices_ticker_fetched", "ticker_id", "fetched_at"),)
