import os
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.repository as repo
from alembic import command
from app.database import Base, get_db
from app.main import app
from app.models import Ticker
from app.repository import PriceData

TEST_DATABASE_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
)

_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

test_engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_db() -> Generator[None, None, None]:
    cfg = Config(str(_ALEMBIC_INI))
    command.upgrade(cfg, "head")
    yield
    Base.metadata.drop_all(bind=test_engine)
    with test_engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")


@pytest.fixture(autouse=True)
def clean_tables(create_test_db: None) -> Generator[None, None, None]:
    """Truncate all tables after every test so each test starts with a clean slate."""
    yield
    with TestingSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def db_session(clean_tables: None) -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_tickers(db_session: Session) -> list[Ticker]:
    """Pre-populate the database with a known set of tickers."""
    ticker_a = repo.create(db_session, "AAPL")
    ticker_b = repo.create(db_session, "MSFT")
    return [ticker_a, ticker_b]


@pytest.fixture
def seeded_articles(db_session: Session, seeded_tickers: list[Ticker]) -> None:
    """Pre-populate the database with articles linked to tickers."""
    articles_data = [
        {
            "url": "https://example.com/apple-article",
            "title": "AAPL hits new high",
            "summary": "Apple stock climbs on strong earnings.",
            "source": "TestSource",
            "published_at": datetime(2026, 4, 28, 10, 0, 0, tzinfo=timezone.utc),
            "ticker_symbols": ["AAPL"],
        },
        {
            "url": "https://example.com/tech-giants-article",
            "title": "Tech giants rally",
            "summary": "Both AAPL and MSFT post gains.",
            "source": "TestSource",
            "published_at": datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc),
            "ticker_symbols": ["AAPL", "MSFT"],
        },
    ]
    repo.upsert_articles(db_session, articles_data)


@pytest.fixture
def seeded_prices(db_session: Session, seeded_tickers: list[Ticker]) -> None:
    """Pre-populate the database with price snapshots for seeded tickers."""
    repo.insert_prices(
        db_session,
        [
            PriceData(
                symbol="AAPL",
                price=175.50,
                open=174.00,
                high=176.00,
                low=173.50,
                volume=55_000_000,
            ),
            PriceData(
                symbol="AAPL",
                price=176.20,
                open=175.50,
                high=177.00,
                low=175.00,
                volume=60_000_000,
            ),
            PriceData(
                symbol="MSFT",
                price=420.10,
                open=418.00,
                high=421.00,
                low=417.50,
                volume=22_000_000,
            ),
        ],
    )
