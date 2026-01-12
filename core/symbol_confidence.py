import math

class SymbolConfidenceEstimator:
    def estimate(
        self,
        symbol: str,
        alternatives: list[str] | None,
        context_score: float,
    ) -> float:
        base = 1.0

        if alternatives and len(alternatives) > 1:
            base -= 0.3

        if symbol in {"1", "l", "I", "O", "0"}:
            base -= 0.2

        base *= context_score
        return round(max(0.0, min(1.0, base)), 3)
