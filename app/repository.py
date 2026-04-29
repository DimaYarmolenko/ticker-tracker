from sqlalchemy.orm import Session

from app.models import Article, Ticker, article_tickers


def get_all(db: Session) -> list[Ticker]:
    return db.query(Ticker).all()


def get_by_symbol(db: Session, symbol: str) -> Ticker | None:
    return db.query(Ticker).filter(Ticker.symbol == symbol).first()


def create(db: Session, symbol: str) -> Ticker:
    ticker = Ticker(symbol=symbol)
    db.add(ticker)
    db.commit()
    db.refresh(ticker)
    return ticker


def delete(db: Session, ticker: Ticker) -> None:
    db.delete(ticker)
    db.commit()


def get_article_by_url(db: Session, url: str) -> Article | None:
    return db.query(Article).filter(Article.url == url).first()


def _articles_for_ticker_query(db: Session, ticker_id: str):
    return (
        db.query(Article)
        .join(article_tickers, Article.id == article_tickers.c.article_id)
        .filter(article_tickers.c.ticker_id == ticker_id)
        .order_by(Article.published_at.desc())
    )


def get_articles_by_symbol(
    db: Session, symbol: str, limit: int = 20, offset: int = 0
) -> list[Article]:
    ticker = get_by_symbol(db, symbol)
    if ticker is None:
        return []
    return _articles_for_ticker_query(db, ticker.id).offset(offset).limit(limit).all()


def count_articles_by_symbol(db: Session, symbol: str) -> int:
    ticker = get_by_symbol(db, symbol)
    if ticker is None:
        return 0
    return _articles_for_ticker_query(db, ticker.id).count()


def upsert_articles(db: Session, articles_data: list[dict]) -> None:
    for data in articles_data:
        existing = get_article_by_url(db, data["url"])
        if existing:
            _attach_tickers(db, existing, data["ticker_symbols"])
            continue
        article = Article(
            url=data["url"],
            title=data["title"],
            summary=data.get("summary"),
            source=data.get("source"),
            published_at=data.get("published_at"),
        )
        db.add(article)
        db.flush()
        _attach_tickers(db, article, data["ticker_symbols"])
    db.commit()


def _attach_tickers(db: Session, article: Article, symbols: list[str]) -> None:
    existing_symbols = {t.symbol for t in article.tickers}
    for symbol in symbols:
        if symbol not in existing_symbols:
            ticker = get_by_symbol(db, symbol)
            if ticker:
                article.tickers.append(ticker)
