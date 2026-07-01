from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi.testclient import TestClient

import app.scheduler as scheduler_mod
from app.config import env_bool, read_int_env
from app.evaluator import ArticleEvaluation, EvaluatorInput, TickerImpact
from app.main import app
from app.models import ImpactLabel
from app.scheduler import (
    SchedulerJobId,
    _poll_evaluations,
    _register_evaluation_job,
)

# --- env_bool ---


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("nonsense", False),
    ],
)
def test_env_bool_parses_truthy_values(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    monkeypatch.setenv("FLAG_X", value)
    assert env_bool("FLAG_X", default=False) is expected


def test_env_bool_unset_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLAG_X", raising=False)
    assert env_bool("FLAG_X", default=False) is False
    assert env_bool("FLAG_X", default=True) is True


# --- read_int_env ---


def test_read_int_env_required_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEEDED", raising=False)
    with pytest.raises(ValueError, match="NEEDED"):
        read_int_env("NEEDED", required=True)


def test_read_int_env_optional_missing_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAYBE", raising=False)
    assert read_int_env("MAYBE", required=False, default=42) == 42


def test_read_int_env_invalid_int_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAD", "abc")
    with pytest.raises(ValueError, match="BAD"):
        read_int_env("BAD", required=True)


# --- _poll_evaluations ---


def _make_article(
    article_id: str, tickers: list[str], title: str = "t", summary: str | None = None
) -> Any:
    ticker_mocks = [MagicMock(symbol=s) for s in tickers]
    article = MagicMock()
    article.id = article_id
    article.title = title
    article.summary = summary
    article.tickers = ticker_mocks
    return article


def test_poll_evaluations_skips_when_no_unevaluated(seeded_tickers: list) -> None:
    evaluator = MagicMock()
    with (
        patch("app.scheduler.repo.get_unevaluated_articles", return_value=[]),
        patch("app.scheduler.repo.save_evaluations") as mock_save,
    ):
        _poll_evaluations(evaluator=evaluator, version="v1", batch_size=10, max_per_run=100)

    evaluator.evaluate.assert_not_called()
    mock_save.assert_not_called()


def test_poll_evaluations_happy_path_calls_save(seeded_tickers: list) -> None:
    articles = [_make_article("a1", ["AAPL"]), _make_article("a2", ["MSFT"])]
    evaluator = MagicMock()
    evaluator.evaluate.return_value = [
        ArticleEvaluation(
            article_id="a1",
            importance=3,
            impacts=[TickerImpact(symbol="AAPL", impact=ImpactLabel.POSITIVE, confidence=0.7)],
        )
    ]
    with (
        patch("app.scheduler.repo.get_unevaluated_articles", return_value=articles),
        patch("app.scheduler.repo.save_evaluations") as mock_save,
    ):
        _poll_evaluations(evaluator=evaluator, version="vX", batch_size=10, max_per_run=100)

    evaluator.evaluate.assert_called_once()
    sent_inputs = evaluator.evaluate.call_args[0][0]
    assert {i.article_id for i in sent_inputs} == {"a1", "a2"}
    mock_save.assert_called_once()
    _, results, version = mock_save.call_args[0]
    assert version == "vX"
    assert len(results) == 1


def test_poll_evaluations_splits_into_batches(seeded_tickers: list) -> None:
    articles = [_make_article(f"a{i}", ["AAPL"]) for i in range(5)]
    evaluator = MagicMock()
    evaluator.evaluate.return_value = []
    with (
        patch("app.scheduler.repo.get_unevaluated_articles", return_value=articles),
        patch("app.scheduler.repo.save_evaluations"),
    ):
        _poll_evaluations(evaluator=evaluator, version="v1", batch_size=2, max_per_run=100)

    # 5 items, batch=2 -> 3 calls (2, 2, 1)
    assert evaluator.evaluate.call_count == 3
    batch_sizes = [len(call.args[0]) for call in evaluator.evaluate.call_args_list]
    assert batch_sizes == [2, 2, 1]


def test_poll_evaluations_partial_failure_persists_successful_batches(
    seeded_tickers: list,
) -> None:
    articles = [_make_article(f"a{i}", ["AAPL"]) for i in range(4)]
    evaluator = MagicMock()
    success_result = ArticleEvaluation(article_id="a0", importance=2, impacts=[])
    # First batch returns one result; second batch returns nothing (failure)
    evaluator.evaluate.side_effect = [[success_result], []]
    with (
        patch("app.scheduler.repo.get_unevaluated_articles", return_value=articles),
        patch("app.scheduler.repo.save_evaluations") as mock_save,
    ):
        _poll_evaluations(evaluator=evaluator, version="v1", batch_size=2, max_per_run=100)

    mock_save.assert_called_once()
    _, results, _ = mock_save.call_args[0]
    assert results == [success_result]


def test_poll_evaluations_no_save_when_all_batches_fail(seeded_tickers: list) -> None:
    articles = [_make_article("a1", ["AAPL"])]
    evaluator = MagicMock()
    evaluator.evaluate.return_value = []
    with (
        patch("app.scheduler.repo.get_unevaluated_articles", return_value=articles),
        patch("app.scheduler.repo.save_evaluations") as mock_save,
    ):
        _poll_evaluations(evaluator=evaluator, version="v1", batch_size=10, max_per_run=100)

    evaluator.evaluate.assert_called_once()
    mock_save.assert_not_called()


def test_poll_evaluations_swallows_repository_exceptions(seeded_tickers: list) -> None:
    evaluator = MagicMock()
    with patch("app.scheduler.repo.get_unevaluated_articles", side_effect=RuntimeError("db boom")):
        # Must not raise — scheduler jobs should never propagate.
        _poll_evaluations(evaluator=evaluator, version="v1", batch_size=10, max_per_run=100)
    evaluator.evaluate.assert_not_called()


def test_poll_evaluations_forwards_input_fields(seeded_tickers: list) -> None:
    article = _make_article("a1", ["AAPL", "MSFT"], title="big news", summary="something")
    evaluator = MagicMock()
    evaluator.evaluate.return_value = []
    with (
        patch("app.scheduler.repo.get_unevaluated_articles", return_value=[article]),
        patch("app.scheduler.repo.save_evaluations"),
    ):
        _poll_evaluations(evaluator=evaluator, version="v1", batch_size=10, max_per_run=100)

    (sent,) = evaluator.evaluate.call_args[0][0]
    assert sent == EvaluatorInput(
        article_id="a1", title="big news", summary="something", ticker_symbols=["AAPL", "MSFT"]
    )


# --- _register_evaluation_job ---


def test_register_evaluation_job_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALUATOR_ENABLED", "false")
    sched = BackgroundScheduler()
    _register_evaluation_job(sched)
    assert sched.get_job(SchedulerJobId.EVALUATE) is None


def test_register_evaluation_job_skipped_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVALUATOR_ENABLED", raising=False)
    sched = BackgroundScheduler()
    _register_evaluation_job(sched)
    assert sched.get_job(SchedulerJobId.EVALUATE) is None


def test_register_evaluation_job_registers_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALUATOR_ENABLED", "true")
    monkeypatch.setenv("EVALUATOR_BACKEND", "noop")
    monkeypatch.setenv("EVALUATION_POLL_INTERVAL_MINUTES", "15")
    monkeypatch.setenv("EVALUATOR_VERSION", "v9")

    sched = BackgroundScheduler()
    _register_evaluation_job(sched)
    job = sched.get_job(SchedulerJobId.EVALUATE)
    assert job is not None
    assert job.kwargs["version"] == "v9"
    assert job.kwargs["batch_size"] == 10
    assert job.kwargs["max_per_run"] == 100


def test_register_evaluation_job_uses_overridden_batch_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVALUATOR_ENABLED", "true")
    monkeypatch.setenv("EVALUATOR_BACKEND", "noop")
    monkeypatch.setenv("EVALUATION_POLL_INTERVAL_MINUTES", "15")
    monkeypatch.setenv("EVALUATOR_BATCH_SIZE", "5")
    monkeypatch.setenv("EVALUATOR_MAX_PER_RUN", "50")

    sched = BackgroundScheduler()
    _register_evaluation_job(sched)
    job = sched.get_job(SchedulerJobId.EVALUATE)
    assert job is not None
    assert job.kwargs["batch_size"] == 5
    assert job.kwargs["max_per_run"] == 50


def test_register_evaluation_job_missing_interval_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALUATOR_ENABLED", "true")
    monkeypatch.delenv("EVALUATION_POLL_INTERVAL_MINUTES", raising=False)
    sched = BackgroundScheduler()
    with pytest.raises(ValueError, match="EVALUATION_POLL_INTERVAL_MINUTES"):
        _register_evaluation_job(sched)


def test_register_evaluation_job_skips_when_evaluator_init_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVALUATOR_ENABLED", "true")
    monkeypatch.setenv("EVALUATION_POLL_INTERVAL_MINUTES", "15")
    sched = BackgroundScheduler()
    with patch("app.scheduler.get_evaluator", side_effect=RuntimeError("init failure")):
        _register_evaluation_job(sched)
    assert sched.get_job(SchedulerJobId.EVALUATE) is None


# --- Test fixture contract: TestClient should NOT boot the scheduler ---


def test_test_client_does_not_start_scheduler() -> None:
    """Locks in the conftest contract: lifespan must stay inert during tests so
    APScheduler doesn't spin up background threads. If someone re-wraps the
    client fixture in `with TestClient(app)`, this test will fail."""
    assert scheduler_mod._scheduler is None
    TestClient(app)  # no `with` — lifespan should not fire
    assert scheduler_mod._scheduler is None
