import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.models import ImpactLabel


@dataclass(frozen=True)
class EvaluatorInput:
    article_id: str
    title: str
    summary: str | None
    ticker_symbols: list[str]


@dataclass(frozen=True)
class TickerImpact:
    symbol: str
    impact: ImpactLabel
    confidence: float


@dataclass(frozen=True)
class ArticleEvaluation:
    article_id: str
    importance: int
    impacts: list[TickerImpact]


class EvaluatorBackend(StrEnum):
    NOOP = "noop"
    GEMINI = "gemini"


class Evaluator(Protocol):
    def evaluate(self, items: list[EvaluatorInput]) -> list[ArticleEvaluation]: ...


def get_evaluator() -> Evaluator:
    raw = os.getenv("EVALUATOR_BACKEND", EvaluatorBackend.NOOP.value).lower()
    try:
        backend = EvaluatorBackend(raw)
    except ValueError as exc:
        raise ValueError(f"Unknown EVALUATOR_BACKEND: {raw!r}") from exc

    if backend is EvaluatorBackend.GEMINI:
        from app.evaluator.gemini_backend import GeminiEvaluator

        return GeminiEvaluator()
    from app.evaluator.noop_backend import NoopEvaluator

    return NoopEvaluator()


__all__ = [
    "ArticleEvaluation",
    "Evaluator",
    "EvaluatorBackend",
    "EvaluatorInput",
    "TickerImpact",
    "get_evaluator",
]
