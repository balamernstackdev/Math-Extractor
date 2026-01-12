import re
from dataclasses import dataclass

@dataclass
class ConfidenceBreakdown:
    ocr: float
    structure: float
    semantic: float
    mathml: float
    visual: float
    final: float

class ConfidenceScorer:
    def score_ocr(self, latex: str) -> float:
        penalties = 0

        if latex.rstrip().endswith("_"):
            penalties += 0.3
        if latex.count("{") != latex.count("}"):
            penalties += 0.3
        if len(latex) < 20:
            penalties += 0.2

        return max(0.0, 1.0 - penalties)

    def score_structure(self, latex: str) -> float:
        if "\\begin{aligned}" in latex or "\\\\" in latex:
            return 1.0

        if "=" in latex and latex.count("=") == 1:
            return 0.8

        return 0.6

    def score_semantic(self, was_reconstructed: bool) -> float:
        # Reconstruction lowers confidence slightly
        return 0.85 if was_reconstructed else 1.0

    def score_mathml(self, mathml: str) -> float:
        if "<math" not in mathml:
            return 0.0
        if "<merror>" in mathml:
            return 0.4
        if "<mtable>" in mathml:
            return 1.0
        return 0.9

    def score_visual(self, bbox: dict) -> float:
        h = bbox.get("h", 0)
        if h > 350:
            return 1.0
        if h > 200:
            return 0.85
        return 0.7

    def compute(
        self,
        latex: str,
        mathml: str,
        bbox: dict,
        was_reconstructed: bool,
    ) -> ConfidenceBreakdown:

        ocr = self.score_ocr(latex)
        structure = self.score_structure(latex)
        semantic = self.score_semantic(was_reconstructed)
        mathml_score = self.score_mathml(mathml)
        visual = self.score_visual(bbox)

        final = round(
            0.30 * ocr +
            0.25 * structure +
            0.20 * semantic +
            0.15 * mathml_score +
            0.10 * visual,
            3
        )

        return ConfidenceBreakdown(
            ocr=ocr,
            structure=structure,
            semantic=semantic,
            mathml=mathml_score,
            visual=visual,
            final=final
        )
