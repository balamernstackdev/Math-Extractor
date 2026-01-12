from dataclasses import dataclass

@dataclass
class PDFConfidenceSummary:
    avg: float
    min: float
    low_ratio: float
    count: int

class PDFConfidenceAggregator:
    def summarize(self, confidences: list[float]):
        if not confidences:
            return PDFConfidenceSummary(0, 0, 0, 0)

        avg = sum(confidences) / len(confidences)
        min_c = min(confidences)
        low_ratio = sum(c < 0.75 for c in confidences) / len(confidences)

        return PDFConfidenceSummary(
            avg=round(avg, 3),
            min=round(min_c, 3),
            low_ratio=round(low_ratio, 3),
            count=len(confidences),
        )
