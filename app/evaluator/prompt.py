import json
import logging
from collections.abc import Iterable

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from app.evaluator import ArticleEvaluation, EvaluatorInput, TickerImpact
from app.models import ImpactLabel

logger = logging.getLogger(__name__)

_SUMMARY_MAX_CHARS = 500

SYSTEM_PROMPT = """You are a financial news analyst.
For each article you receive, decide:

1. importance — how market-moving the news is, on a 1-5 integer scale:
   1 = noise / routine
   2 = minor color
   3 = notable
   4 = significant
   5 = market-moving / urgent

2. impacts — for EVERY entry in that article's ticker_symbols, judge the
   likely directional effect on that stock.

Output schema (use these exact JSON keys — no synonyms):
{
  "results": [
    {
      "article_id": "<echo from input>",
      "importance": 1..5,
      "impacts": [
        {
          "symbol": "<TICKER>",
          "impact": "positive" | "negative" | "neutral",
          "confidence": 0.0..1.0
        }
      ]
    }
  ]
}

Do NOT rename fields. Keys must be exactly: symbol, impact, confidence
(not ticker_symbol, not sentiment, not direction). Return only the JSON
object — no prose, no markdown fences."""


class _ImpactItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(validation_alias=AliasChoices("symbol", "ticker_symbol", "ticker"))
    impact: ImpactLabel = Field(validation_alias=AliasChoices("impact", "sentiment", "direction"))
    confidence: float = Field(ge=0.0, le=1.0)


class _ArticleResult(BaseModel):
    article_id: str
    importance: int = Field(ge=1, le=5)
    impacts: list[_ImpactItem]


class EvaluationResponse(BaseModel):
    results: list[_ArticleResult]


def format_user_message(items: Iterable[EvaluatorInput]) -> str:
    payload = [
        {
            "article_id": it.article_id,
            "title": it.title,
            "summary": (it.summary or "")[:_SUMMARY_MAX_CHARS],
            "ticker_symbols": list(it.ticker_symbols),
        }
        for it in items
    ]
    return json.dumps(payload, ensure_ascii=False)


def parse_response(raw_json: str) -> list[ArticleEvaluation]:
    try:
        parsed = EvaluationResponse.model_validate_json(raw_json)
    except ValidationError as exc:
        logger.warning("Evaluator response failed validation: %s", exc)
        return []

    return [
        ArticleEvaluation(
            article_id=r.article_id,
            importance=r.importance,
            impacts=[
                TickerImpact(symbol=i.symbol, impact=i.impact, confidence=i.confidence)
                for i in r.impacts
            ],
        )
        for r in parsed.results
    ]
