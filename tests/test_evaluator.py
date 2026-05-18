import json
from unittest.mock import MagicMock

import pytest

from app.evaluator import (
    ArticleEvaluation,
    EvaluatorInput,
    TickerImpact,
    get_evaluator,
)
from app.evaluator.gemini_backend import GeminiEvaluator
from app.evaluator.noop_backend import NoopEvaluator
from app.evaluator.prompt import format_user_message, parse_response
from app.models import ImpactLabel

# --- prompt.format_user_message ---


def test_format_user_message_serializes_each_field() -> None:
    items = [
        EvaluatorInput(
            article_id="id-1",
            title="AAPL earnings beat",
            summary="Apple beat estimates by 5%.",
            ticker_symbols=["AAPL"],
        )
    ]
    raw = format_user_message(items)
    payload = json.loads(raw)
    assert payload == [
        {
            "article_id": "id-1",
            "title": "AAPL earnings beat",
            "summary": "Apple beat estimates by 5%.",
            "ticker_symbols": ["AAPL"],
        }
    ]


def test_format_user_message_truncates_long_summary() -> None:
    long_summary = "x" * 1000
    items = [EvaluatorInput(article_id="id", title="t", summary=long_summary, ticker_symbols=["A"])]
    payload = json.loads(format_user_message(items))
    assert len(payload[0]["summary"]) == 500


def test_format_user_message_handles_none_summary() -> None:
    items = [EvaluatorInput(article_id="id", title="t", summary=None, ticker_symbols=["A"])]
    payload = json.loads(format_user_message(items))
    assert payload[0]["summary"] == ""


# --- prompt.parse_response ---


def test_parse_response_valid_json() -> None:
    raw = json.dumps(
        {
            "results": [
                {
                    "article_id": "a1",
                    "importance": 4,
                    "impacts": [
                        {"symbol": "AAPL", "impact": "positive", "confidence": 0.85},
                    ],
                }
            ]
        }
    )
    results = parse_response(raw)
    assert results == [
        ArticleEvaluation(
            article_id="a1",
            importance=4,
            impacts=[TickerImpact(symbol="AAPL", impact=ImpactLabel.POSITIVE, confidence=0.85)],
        )
    ]


def test_parse_response_invalid_json_returns_empty() -> None:
    assert parse_response("not json at all") == []


def test_parse_response_missing_results_key_returns_empty() -> None:
    assert parse_response(json.dumps({"foo": "bar"})) == []


def test_parse_response_importance_out_of_range_returns_empty() -> None:
    raw = json.dumps(
        {
            "results": [
                {"article_id": "a1", "importance": 99, "impacts": []},
            ]
        }
    )
    assert parse_response(raw) == []


def test_parse_response_invalid_impact_label_returns_empty() -> None:
    raw = json.dumps(
        {
            "results": [
                {
                    "article_id": "a1",
                    "importance": 3,
                    "impacts": [{"symbol": "AAPL", "impact": "wat", "confidence": 0.5}],
                }
            ]
        }
    )
    assert parse_response(raw) == []


def test_parse_response_accepts_ticker_symbol_alias() -> None:
    raw = json.dumps(
        {
            "results": [
                {
                    "article_id": "a1",
                    "importance": 3,
                    "impacts": [
                        {"ticker_symbol": "AAPL", "sentiment": "neutral", "confidence": 0.8},
                    ],
                }
            ]
        }
    )
    results = parse_response(raw)
    assert len(results) == 1
    assert results[0].impacts[0].symbol == "AAPL"
    assert results[0].impacts[0].impact is ImpactLabel.NEUTRAL


def test_parse_response_confidence_out_of_range_returns_empty() -> None:
    raw = json.dumps(
        {
            "results": [
                {
                    "article_id": "a1",
                    "importance": 3,
                    "impacts": [{"symbol": "AAPL", "impact": "positive", "confidence": 2.0}],
                }
            ]
        }
    )
    assert parse_response(raw) == []


# --- NoopEvaluator ---


def test_noop_evaluator_returns_empty() -> None:
    evaluator = NoopEvaluator()
    inputs = [EvaluatorInput(article_id="id", title="t", summary=None, ticker_symbols=["A"])]
    assert evaluator.evaluate(inputs) == []


# --- get_evaluator factory ---


def test_get_evaluator_default_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVALUATOR_BACKEND", raising=False)
    assert isinstance(get_evaluator(), NoopEvaluator)


def test_get_evaluator_noop_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALUATOR_BACKEND", "noop")
    assert isinstance(get_evaluator(), NoopEvaluator)


def test_get_evaluator_unknown_backend_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALUATOR_BACKEND", "mystery")
    with pytest.raises(ValueError, match="mystery"):
        get_evaluator()


def test_get_evaluator_gemini_without_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALUATOR_BACKEND", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        get_evaluator()


# --- GeminiEvaluator ---


def _make_fake_client(text: str) -> MagicMock:
    fake_response = MagicMock()
    fake_response.text = text
    client = MagicMock()
    client.models.generate_content.return_value = fake_response
    return client


def test_gemini_evaluator_empty_input_skips_api_call() -> None:
    client = MagicMock()
    evaluator = GeminiEvaluator(client=client, model="gemini-2.5-flash")
    assert evaluator.evaluate([]) == []
    client.models.generate_content.assert_not_called()


def test_gemini_evaluator_returns_parsed_results() -> None:
    raw = json.dumps(
        {
            "results": [
                {
                    "article_id": "a1",
                    "importance": 5,
                    "impacts": [
                        {"symbol": "MSFT", "impact": "negative", "confidence": 0.7},
                    ],
                }
            ]
        }
    )
    client = _make_fake_client(raw)
    evaluator = GeminiEvaluator(client=client, model="gemini-2.5-flash")
    inputs = [EvaluatorInput(article_id="a1", title="t", summary=None, ticker_symbols=["MSFT"])]

    result = evaluator.evaluate(inputs)

    assert len(result) == 1
    assert result[0].article_id == "a1"
    assert result[0].importance == 5
    assert result[0].impacts[0].impact is ImpactLabel.NEGATIVE
    client.models.generate_content.assert_called_once()


def test_gemini_evaluator_passes_system_instruction_and_json_mode() -> None:
    client = _make_fake_client(json.dumps({"results": []}))
    evaluator = GeminiEvaluator(client=client, model="gemini-2.5-flash")
    inputs = [EvaluatorInput(article_id="a1", title="t", summary=None, ticker_symbols=["AAPL"])]

    evaluator.evaluate(inputs)

    _, kwargs = client.models.generate_content.call_args
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["config"]["response_mime_type"] == "application/json"
    assert kwargs["config"]["response_schema"] is not None
    assert "financial news analyst" in kwargs["config"]["system_instruction"].lower()


def test_gemini_evaluator_empty_text_returns_empty() -> None:
    client = _make_fake_client("")
    evaluator = GeminiEvaluator(client=client, model="gemini-2.5-flash")
    inputs = [EvaluatorInput(article_id="a1", title="t", summary=None, ticker_symbols=["AAPL"])]
    assert evaluator.evaluate(inputs) == []


def test_gemini_evaluator_malformed_json_returns_empty() -> None:
    client = _make_fake_client("garbage }{")
    evaluator = GeminiEvaluator(client=client, model="gemini-2.5-flash")
    inputs = [EvaluatorInput(article_id="a1", title="t", summary=None, ticker_symbols=["AAPL"])]
    assert evaluator.evaluate(inputs) == []


def test_gemini_evaluator_api_error_returns_empty() -> None:
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("rate limit")
    evaluator = GeminiEvaluator(client=client, model="gemini-2.5-flash")
    inputs = [EvaluatorInput(article_id="a1", title="t", summary=None, ticker_symbols=["AAPL"])]
    assert evaluator.evaluate(inputs) == []
