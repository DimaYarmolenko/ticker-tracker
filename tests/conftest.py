import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.repository as repo
from app.database import Base, get_db
from app.main import app
from app.models import Ticker

TEST_DATABASE_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
)

test_engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_db() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_tickers(db_session: Session) -> list[Ticker]:
    """Pre-populate the database with a known set of tickers."""
    ticker_a = repo.create(db_session, "AAPL")
    ticker_b = repo.create(db_session, "MSFT")
    return [ticker_a, ticker_b]
