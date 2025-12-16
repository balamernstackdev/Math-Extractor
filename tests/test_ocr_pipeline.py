"""Tests for the unified MathML/LaTeX/plain ingestion pipeline."""
from __future__ import annotations

from services.ocr.pipeline import MathExpressionPipeline
from services.ocr.latex_to_mathml import LatexToMathML


def test_ingest_mathml_fraction() -> None:
    pipeline = MathExpressionPipeline()
    raw = '<math xmlns="http://www.w3.org/1998/Math/MathML"><mfrac><mi>a</mi><mi>b</mi></mfrac></math>'

    result = pipeline.ingest(raw)

    assert result["source_type"] == "mathml"
    assert r"\frac" in result["clean_latex"]
    assert "<math" in result["mathml"]


def test_ingest_latex_pass_through() -> None:
    pipeline = MathExpressionPipeline()
    raw = r"\frac{1}{n} \sum_{t=0}^{n-1} x_t^2"

    result = pipeline.ingest(raw)

    assert result["source_type"] == "latex"
    assert r"\frac{1}{n}" in result["clean_latex"]
    assert "<math" in result["mathml"]


def test_ingest_plain_reconstructs() -> None:
    pipeline = MathExpressionPipeline()
    raw = "1/n sum_{i=1}^{n} x_i"

    result = pipeline.ingest(raw)

    assert result["source_type"] == "plain"
    assert r"\frac{1}{n}" in result["clean_latex"]
    assert r"\sum_{i=1}^{n}" in result["clean_latex"]
    assert "<math" in result["mathml"]


def test_mathml_scripts_and_ranges_rebuilt() -> None:
    pipeline = MathExpressionPipeline()
    raw = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        "<mrow><mi>x</mi><mo>_</mo><mi>i</mi><mo>=</mo><mn>1</mn><mo>^</mo><mi>K</mi></mrow>"
        "</math>"
    )

    result = pipeline.ingest(raw)

    assert result["source_type"] == "mathml"
    assert r"x_{i=1}^{K}" in result["clean_latex"]
    assert "<msubsup>" in result["intermediate_mathml"]


def test_mathml_brackets_and_limits_repaired() -> None:
    pipeline = MathExpressionPipeline()
    raw = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML">'
        "<mrow><mo>∑</mo><mo>_</mo><mi>i</mi><mo>=</mo><mn>1</mn><mo>^</mo><mi>n</mi>"
        "<mo>(</mo><mi>a</mi><mi>i</mi></mrow>"
        "</math>"
    )

    result = pipeline.ingest(raw)

    assert result["source_type"] == "mathml"
    # Closing bracket should be synthesized
    assert "<mo>)</mo>" in result["intermediate_mathml"]
    # Sum limits should be attached as sub/sup
    assert r"\sum_{i=1}^{n}" in result["clean_latex"]


def test_mathml_munder_sum_converts_to_latex_limits() -> None:
    pipeline = MathExpressionPipeline()
    raw = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'
        "<mrow>"
        "<msub><mi>Y</mi><mi>j</mi></msub><mo>[</mo><mi>t</mi><mo>]</mo>"
        "<mo>=</mo>"
        "<munder>"
        "<mo>&#x2211;</mo>"
        "<mrow><mi>i</mi><mo>&#x2208;</mo><mi>I</mi><mo>(</mo><mi>j</mi><mo>)</mo></mrow>"
        "</munder>"
        "<msub><mi>h</mi><mrow><mi>i</mi><mo>,</mo><mi>j</mi></mrow></msub><mo>[</mo><mi>t</mi><mo>]</mo>"
        "<msub><mi>X</mi><mi>i</mi></msub><mo>[</mo><mi>t</mi><mo>]</mo>"
        "<mo>+</mo>"
        "<msub><mi>Z</mi><mi>j</mi></msub>"
        "</mrow></math>"
    )

    result = pipeline.ingest(raw)

    assert result["source_type"] == "mathml"
    assert r"\sum_{i\in I(j)}" in result["clean_latex"]
    assert r"Y_{j}" in result["clean_latex"]
    assert r"[t]" in result["clean_latex"]


def test_mathml_prob_union_noise_repaired() -> None:
    pipeline = MathExpressionPipeline()
    raw = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'
        "<mrow>"
        "<mi>K</mi>"
        "<msub><mi>P</mi><mi>e</mi></msub>"
        "<msub><mi>r</mi><mi>r</mi></msub>"
        "<msub><mi>o</mi><mi>r</mi></msub>"
        "<mo>(</mo><mi>C</mi><mo>)</mo>"
        "<mo>=</mo>"
        "<msub><mi>\\P</mi><mi>r</mi></msub>"
        "<msub><mi>U</mi><mi>m</mi></msub>"
        "<mi>#</mi><mn>9</mn><mi>:</mi>"
        "<mo>(</mo><msub><mi>Y</mi><mi>a</mi></msub><mo>,</mo><mo>[</mo><mn>0</mn><mo>]</mo><mo>,</mo><mi>a</mi><msub><mi>Y</mi><mi>a</mi></msub><mi>;</mi><mo>[</mo><mi>n</mi><mn>1</mn><mo>)</mo><mo>)</mo><mo>}</mo><mo>?</mo><mi>i</mi><mo>=</mo><mn>1</mn>"
        "</mrow></math>"
    )

    result = pipeline.ingest(raw)

    assert result["source_type"] == "mathml"
    assert r"P_{r}" in result["clean_latex"]
    assert r"\cup" in result["clean_latex"]
    assert "#" not in result["clean_latex"]
    assert r"Y_{a}" in result["clean_latex"]


def test_detect_probability_of_error_template_json() -> None:
    converter = LatexToMathML()
    noisy = r"P_error(C) = P r[ W i 4 g i (Y a, 0], ..., Y a; l n - 1 ])"

    detected = converter.detect_probability_of_error(noisy)

    assert detected is not None
    assert detected["detected_template"] == "probability_of_error"
    assert detected["fixed_latex"].startswith(r"P_{\text{error}}(C)")
    assert 0.5 <= detected["confidence"] <= 1.0


def test_latex_channel_noise_repaired_basic() -> None:
    converter = LatexToMathML()
    noisy = r"$Y_{j}l_{e}]= d_{S}) h_{a}y] X_{i}[e] + Z;[e, 4T (7)$"

    cleaned = converter._repair_common_ocr_errors(noisy)

    assert "[t]" in cleaned
    assert "Z" in cleaned
    assert "4T" not in cleaned


def test_latex_channel_noise_snaps_to_canonical() -> None:
    converter = LatexToMathML()
    noisy = r"$Y_{i}l] = D> h_{a} g_{l}] X_{i}l_{e}] + Z;[t). i_{T}L (7)$"

    repaired = converter._repair_common_ocr_errors(noisy)
    assert converter.CHANNEL_CANONICAL in repaired


def test_latex_channel_noise_variant_hits_canonical() -> None:
    converter = LatexToMathML()
    noisy = r"$Y_{l} = S_{S} b_{i}l X_{i}l_{e}] + Z_{l}. i_{L}(j)$"

    repaired = converter._repair_common_ocr_errors(noisy)
    assert converter.CHANNEL_CANONICAL in repaired


def test_latex_channel_noise_variant_with_numbers_hits_canonical() -> None:
    converter = LatexToMathML()
    noisy = r"$Y_{i}l_{l}= S_{P} h_{a}g X_{i}l_{d}] + 251d) #2(9)$"

    repaired = converter._repair_common_ocr_errors(noisy)
    assert converter.CHANNEL_CANONICAL in repaired


def test_general_noise_brackets_and_equals_cleanup() -> None:
    converter = LatexToMathML()
    noisy = r"$K C_{s}(P) = (R: g_{r}e_{e}s C(P) S_{s} u_{v} i=l$"

    repaired = converter._repair_common_ocr_errors(noisy)
    assert "(R" not in repaired
    assert "i=l" not in repaired


def test_general_noise_numbers_and_question_removed() -> None:
    converter = LatexToMathML()
    noisy = r"$K C_{s}(P) = n X_{x} S_{s} u_{v} (R_{i} g_{r}e_{e}s )e_{C}(P) i=l$"

    repaired = converter._repair_common_ocr_errors(noisy)
    assert "i=l" not in repaired
    assert "(R" not in repaired
    assert " n " not in repaired


def test_prob_error_template_snap() -> None:
    converter = LatexToMathML()
    noisy = r"$K P_{e}r_{r}o_{r}(C) = \\P_{r} U_{t}i # g_{i}(Y_{a};[0],-.-, Y_{a},[[n])}] i=1$"

    repaired = converter._repair_common_ocr_errors(noisy)
    assert converter.PROB_ERROR_CANONICAL == repaired


def test_mathml_munder_sum_converts_to_latex_limits() -> None:
    pipeline = MathExpressionPipeline()
    raw = (
        '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'
        "<mrow>"
        "<msub><mi>Y</mi><mi>j</mi></msub><mo>[</mo><mi>t</mi><mo>]</mo>"
        "<mo>=</mo>"
        "<munder>"
        "<mo>&#x2211;</mo>"
        "<mrow><mi>i</mi><mo>&#x2208;</mo><mi>I</mi><mo>(</mo><mi>j</mi><mo>)</mo></mrow>"
        "</munder>"
        "<msub><mi>h</mi><mrow><mi>i</mi><mo>,</mo><mi>j</mi></mrow></msub><mo>[</mo><mi>t</mi><mo>]</mo>"
        "<msub><mi>X</mi><mi>i</mi></msub><mo>[</mo><mi>t</mi><mo>]</mo>"
        "<mo>+</mo>"
        "<msub><mi>Z</mi><mi>j</mi></msub>"
        "</mrow></math>"
    )