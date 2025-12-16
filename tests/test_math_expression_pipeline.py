import pytest
from unittest.mock import MagicMock, patch

from services.ocr.pipeline import MathExpressionPipeline
from services.ocr.dynamic_latex_reconstructor import DynamicLaTeXReconstructor
from services.ocr.latex_to_mathml import LatexToMathML
from services.ocr.ocr_mathml_cleaner import OCRMathMLCleaner


# ----------------------------------------------------------
# FIXTURES
# ----------------------------------------------------------

@pytest.fixture
def pipeline():
    """Create a fully wired pipeline instance."""
    return MathExpressionPipeline(
        reconstructor=DynamicLaTeXReconstructor(),
        mathml_converter=LatexToMathML(),
        mathml_cleaner=OCRMathMLCleaner()
    )


# ----------------------------------------------------------
# INPUT TYPE DETECTION TESTS
# ----------------------------------------------------------

def test_detect_mathml(pipeline):
    assert pipeline.detect_input_type("<math><mi>x</mi></math>") == "mathml"
    assert pipeline.detect_input_type("<mrow><mi>a</mi>") == "mathml"


def test_detect_latex(pipeline):
    assert pipeline.detect_input_type(r"\frac{1}{n}") == "latex"
    assert pipeline.detect_input_type("x_i + y^2") == "latex"
    assert pipeline.detect_input_type("$x+y$") == "latex"


def test_detect_plain_text(pipeline):
    assert pipeline.detect_input_type("This is OCR text 123") == "plain"


def test_detect_empty(pipeline):
    assert pipeline.detect_input_type("") == "empty"
    assert pipeline.detect_input_type("   ") == "empty"


# ----------------------------------------------------------
# CLEAN MATHML PATH (NO RECOVERY)
# ----------------------------------------------------------

def test_clean_mathml_pass_through(pipeline):
    good_mathml = "<math><mrow><mi>x</mi><mo>=</mo><mn>2</mn></mrow></math>"
    
    result = pipeline.ingest(good_mathml)
    
    assert result["source_type"] == "mathml"
    assert "<math" in result["mathml"]
    assert result["clean_latex"] == ""  # no LaTeX generated


# ----------------------------------------------------------
# CORRUPTED MATHML → RECOVERY PATH
# ----------------------------------------------------------

def test_corrupted_mathml_triggers_recovery(pipeline):
    corrupted = """
        <math><mi>l</mi><mi>e</mi><mi>f</mi><mi>t</mi>
        <mi>r</mi><mi>i</mi><mi>g</mi><mi>h</mi><mi>t</mi></math>
    """

    mock_recovery_result = {
        "status": "ok",
        "clean_latex": r"Y_j[t] = \sum_{i} h_{ij}(t) X_i[t] + Z_j[t]",
        "clean_mathml": "<math><mrow><mi>x</mi></mrow></math>",
        "confidence": 0.88,
        "log": ["Recovered OK"]
    }

    with patch("services.ocr.pipeline.recover_from_mathml", return_value=mock_recovery_result):
        result = pipeline.ingest(corrupted)

    assert result["source_type"] == "mathml"
    assert result["mathml"] == mock_recovery_result["clean_mathml"]
    assert result["clean_latex"] == mock_recovery_result["clean_latex"]


# ----------------------------------------------------------
# LATEX PATH → RECONSTRUCTOR → MATHML
# ----------------------------------------------------------

def test_latex_processing(pipeline):
    latex = r"\frac{1}{n} \sum_{t=0}^{n-1} x_t"
    
    result = pipeline.ingest(latex)

    assert result["source_type"] == "latex"
    assert "mfrac" in result["mathml"] or "<math" in result["mathml"]
    assert r"\frac" in result["clean_latex"]


# ----------------------------------------------------------
# PLAIN TEXT PATH → RECONSTRUCTOR → MATHML
# ----------------------------------------------------------

def test_plain_text_processing(pipeline):
    plain = "1 divided by n sum from t equals 0 to n minus 1"
    
    result = pipeline.ingest(plain)

    assert result["source_type"] == "plain"
    assert "<math" in result["mathml"]
    assert result["clean_latex"] != ""


# ----------------------------------------------------------
# LATEX → MathML CONVERSION FAILURE RETURNS SAFE MATHML
# ----------------------------------------------------------

def test_mathml_conversion_failure_returns_safe_math(pipeline):
    with patch.object(
        pipeline.mathml_converter, 
        "convert", 
        side_effect=Exception("Conversion failed")
    ):
        result = pipeline.ingest(r"\frac{1}{n}")

    assert result["source_type"] == "latex"
    assert 'data-error="conversion-failed"' in result["mathml"]


# ----------------------------------------------------------
# RECOVERY MODULE NOT INSTALLED → FALLBACK
# ----------------------------------------------------------

def test_recovery_not_available(pipeline):
    corrupted_mathml = "<math><mi>l</mi><mi>e</mi><mi>f</mi><mi>t</mi></math>"

    with patch("services.ocr.pipeline.recover_from_mathml", None):
        result = pipeline.ingest(corrupted_mathml)

    assert result["source_type"] == "mathml"
    assert "data-error" in result["mathml"]
