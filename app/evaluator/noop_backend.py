from app.evaluator import ArticleEvaluation, EvaluatorInput


class NoopEvaluator:
    def evaluate(self, items: list[EvaluatorInput]) -> list[ArticleEvaluation]:
        return []
