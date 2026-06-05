from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.repository as repo
from app.auth import hash_password


def test_subscribe_is_idempotent(db_session: Session, seeded_user) -> None:
    ticker = repo.get_or_create(db_session, "AAPL")
    assert repo.subscribe(db_session, seeded_user.id, ticker) is True
    assert repo.subscribe(db_session, seeded_user.id, ticker) is False
    assert len(repo.list_subscribed_tickers(db_session, seeded_user.id)) == 1


def test_unsubscribe_returns_false_when_missing(db_session: Session, seeded_user) -> None:
    ticker = repo.get_or_create(db_session, "AAPL")
    assert repo.unsubscribe(db_session, seeded_user.id, ticker.id) is False


def test_unsubscribe_removes_only_join_row(db_session: Session, seeded_user) -> None:
    ticker = repo.get_or_create(db_session, "AAPL")
    repo.subscribe(db_session, seeded_user.id, ticker)
    assert repo.unsubscribe(db_session, seeded_user.id, ticker.id) is True
    # Ticker itself must survive — another user could subscribe to it later.
    assert repo.get_by_symbol(db_session, "AAPL") is not None


def test_list_subscribed_isolates_users(db_session: Session, seeded_user) -> None:
    user_b = repo.create_user(db_session, "other@example.com", hash_password("super-secret"))
    aapl = repo.get_or_create(db_session, "AAPL")
    msft = repo.get_or_create(db_session, "MSFT")
    repo.subscribe(db_session, seeded_user.id, aapl)
    repo.subscribe(db_session, user_b.id, msft)

    a_symbols = {t.symbol for t in repo.list_subscribed_tickers(db_session, seeded_user.id)}
    b_symbols = {t.symbol for t in repo.list_subscribed_tickers(db_session, user_b.id)}
    assert a_symbols == {"AAPL"}
    assert b_symbols == {"MSFT"}


def test_get_or_create_returns_existing_ticker(db_session: Session) -> None:
    first = repo.get_or_create(db_session, "AAPL")
    again = repo.get_or_create(db_session, "AAPL")
    assert first.id == again.id


def test_two_users_can_share_a_ticker(db_session: Session, seeded_user) -> None:
    user_b = repo.create_user(db_session, "other@example.com", hash_password("super-secret"))
    aapl = repo.get_or_create(db_session, "AAPL")
    assert repo.subscribe(db_session, seeded_user.id, aapl) is True
    assert repo.subscribe(db_session, user_b.id, aapl) is True
    assert repo.is_subscribed(db_session, seeded_user.id, aapl.id)
    assert repo.is_subscribed(db_session, user_b.id, aapl.id)


def test_unsubscribe_one_user_does_not_affect_other(
    db_session: Session, seeded_user, anon_client: TestClient
) -> None:
    user_b = repo.create_user(db_session, "other@example.com", hash_password("super-secret"))
    aapl = repo.get_or_create(db_session, "AAPL")
    repo.subscribe(db_session, seeded_user.id, aapl)
    repo.subscribe(db_session, user_b.id, aapl)

    repo.unsubscribe(db_session, seeded_user.id, aapl.id)

    assert not repo.is_subscribed(db_session, seeded_user.id, aapl.id)
    assert repo.is_subscribed(db_session, user_b.id, aapl.id)
    # And the global ticker row itself is untouched.
    assert repo.get_by_symbol(db_session, "AAPL") is not None
