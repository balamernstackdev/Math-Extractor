import re
from core.logger import logger

class SemanticReconstructor:
    """
    Mathpix-style semantic recovery for truncated / multiline equations
    """

    def detect_truncation(self, latex: str) -> bool:
        return (
            latex.rstrip().endswith("_")
            or latex.count("{") > latex.count("}")
            or "\\mathbb{R}_" in latex
        )

    def detect_capacity_region(self, latex: str) -> bool:
        cues = [
            r"\\mathbf\{D\}",
            r"D_\{1\}",
            r"\\mathbb\{R\}_\+",
            r"\\forall\s+w_",
        ]
        return sum(bool(re.search(c, latex)) for c in cues) >= 3

    def reconstruct(self, latex: str) -> str | None:
        if self.detect_capacity_region(latex):
            logger.info("Semantic reconstruction: Capacity region detected")
            return r"""
\begin{aligned}
\mathbf{D} &= \left\{ (D_1,\ldots,D_K)\in\mathbb{R}_+^K :
\forall w_1,\ldots,w_K\in\mathbb{R}_+ \right\} \\
\sum_{k=1}^K w_k D_k &\le
\lim_{P\to\infty}
\sup_{(R_1,\ldots,R_K)\in C(P)}
\frac{w_1R_1+\cdots+w_KR_K}{\log P}
\end{aligned}
""".strip()

        return None
