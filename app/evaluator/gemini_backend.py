import logging
import os

from google import genai

from app.evaluator import ArticleEvaluation, EvaluatorInput
from app.evaluator.prompt import (
    SYSTEM_PROMPT,
    EvaluationResponse,
    format_user_message,
    parse_response,
)

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiEvaluator:
    def __init__(self, client: genai.Client | None = None, model: str | None = None) -> None:
        if client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY env var is required for gemini backend")
            client = genai.Client(api_key=api_key)
        self._client = client
        self._model = model or os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)

    def evaluate(self, items: list[EvaluatorInput]) -> list[ArticleEvaluation]:
        if not items:
            return []

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=format_user_message(items),
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": EvaluationResponse,
                },
            )
        except Exception:
            logger.exception("Gemini request failed for %d article(s)", len(items))
            return []

        text = (getattr(response, "text", None) or "").strip()
        if not text:
            logger.warning("Gemini returned empty response for %d article(s)", len(items))
            return []

        return parse_response(text)
