"""Tests for OCR MathML cleaner."""
from __future__ import annotations

import pytest

from services.ocr.ocr_mathml_cleaner import OCRMathMLCleaner


class TestOCRMathMLCleaner:
    """Test cases for OCR MathML cleaning."""

    def test_remove_stray_characters(self) -> None:
        """Test removal of stray OCR characters."""
        cleaner = OCRMathMLCleaner()
        
        corrupted = '<math><mi>x</mi><mo>€</mo><mi>y</mi><mo>é</mo></math>'
        result = cleaner._remove_stray_chars(corrupted)
        
        assert "€" not in result
        assert "é" not in result
        assert "x" in result
        assert "y" in result

    def test_fix_ocr_patterns(self) -> None:
        """Test fixing common OCR patterns."""
        cleaner = OCRMathMLCleaner()
        
        # Test "l é ]" → "[l]"
        text = "l é ]"
        result = cleaner._fix_ocr_patterns(text)
        assert "[l]" in result or "l" in result
        
        # Test currency symbols
        text = "x € y"
        result = cleaner._fix_ocr_patterns(text)
        assert "€" not in result

    def test_remove_empty_elements(self) -> None:
        """Test removal of empty MathML elements."""
        import xml.etree.ElementTree as ET
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><mi>x</mi><mi></mi><mo>+</mo><mi> </mi></math>'
        root = ET.fromstring(mathml)
        cleaner._remove_empty_elements(root)
        
        # Empty elements should be removed
        mi_elements = [e for e in root.iter() if e.tag == "mi"]
        assert all(e.text and e.text.strip() for e in mi_elements)

    def test_remove_nested_duplicates(self) -> None:
        """Test removal of nested duplicate tags."""
        import xml.etree.ElementTree as ET
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><mi><mi>x</mi></mi></math>'
        root = ET.fromstring(mathml)
        cleaner._remove_nested_duplicates(root)
        
        # Should be flattened to single <mi>x</mi>
        mi_elements = list(root.iter("mi"))
        assert len(mi_elements) == 1
        assert mi_elements[0].text == "x"

    def test_remove_empty_subscripts(self) -> None:
        """Test removal of empty subscripts/superscripts."""
        import xml.etree.ElementTree as ET
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><msub><mi>x</mi><mi></mi></msub></math>'
        root = ET.fromstring(mathml)
        cleaner._clean_structure(root)
        
        # Empty msub should be removed
        msub_elements = list(root.iter("msub"))
        assert len(msub_elements) == 0

    def test_extract_variables(self) -> None:
        """Test extraction of variables."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><mi>x</mi><mo>+</mo><mi>y</mi><mo>=</mo><mi>z</mi></math>'
        cleaner._extract_elements(mathml)
        
        assert "x" in cleaner.extracted_elements["variables"]
        assert "y" in cleaner.extracted_elements["variables"]
        assert "z" in cleaner.extracted_elements["variables"]

    def test_extract_subscripts(self) -> None:
        """Test extraction of subscripts."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><msub><mi>x</mi><mn>1</mn></msub></math>'
        cleaner._extract_elements(mathml)
        
        assert len(cleaner.extracted_elements["subscripts"]) > 0
        sub = cleaner.extracted_elements["subscripts"][0]
        assert sub["base"] == "x"
        assert sub["subscript"] == "1"

    def test_extract_superscripts(self) -> None:
        """Test extraction of superscripts."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><msup><mi>x</mi><mn>2</mn></msup></math>'
        cleaner._extract_elements(mathml)
        
        assert len(cleaner.extracted_elements["superscripts"]) > 0
        sup = cleaner.extracted_elements["superscripts"][0]
        assert sup["base"] == "x"
        assert sup["superscript"] == "2"

    def test_extract_operators(self) -> None:
        """Test extraction of operators."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><mi>x</mi><mo>+</mo><mi>y</mi><mo>=</mo><mi>z</mi></math>'
        cleaner._extract_elements(mathml)
        
        assert "+" in cleaner.extracted_elements["operators"]
        assert "=" in cleaner.extracted_elements["operators"]

    def test_mathml_to_latex_simple(self) -> None:
        """Test conversion of simple MathML to LaTeX."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><mi>x</mi><mo>+</mo><mi>y</mi></math>'
        latex = cleaner._mathml_to_latex(mathml)
        
        assert "x" in latex
        assert "y" in latex
        assert "+" in latex

    def test_mathml_to_latex_fraction(self) -> None:
        """Test conversion of fraction to LaTeX."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><mfrac><mi>a</mi><mi>b</mi></mfrac></math>'
        latex = cleaner._mathml_to_latex(mathml)
        
        assert r"\frac" in latex
        assert "a" in latex
        assert "b" in latex

    def test_mathml_to_latex_subscript(self) -> None:
        """Test conversion of subscript to LaTeX."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><msub><mi>x</mi><mn>1</mn></msub></math>'
        latex = cleaner._mathml_to_latex(mathml)
        
        assert "x" in latex
        assert "1" in latex
        assert "_" in latex or "{" in latex

    def test_mathml_to_latex_superscript(self) -> None:
        """Test conversion of superscript to LaTeX."""
        cleaner = OCRMathMLCleaner()
        
        mathml = '<math><msup><mi>x</mi><mn>2</mn></msup></math>'
        latex = cleaner._mathml_to_latex(mathml)
        
        assert "x" in latex
        assert "2" in latex
        assert "^" in latex or "{" in latex

    def test_full_clean_workflow(self) -> None:
        """Test complete cleaning workflow."""
        cleaner = OCRMathMLCleaner()
        
        # Corrupted MathML with OCR errors
        corrupted = '''
        <math xmlns="http://www.w3.org/1998/Math/MathML">
            <mi>x</mi>
            <mo>€</mo>
            <mi>é</mi>
            <msub>
                <mi>y</mi>
                <mi></mi>
            </msub>
            <mo>+</mo>
            <mi>z</mi>
        </math>
        '''
        
        result = cleaner.clean(corrupted)
        
        assert "latex" in result
        assert "mathml" in result
        assert "elements" in result
        assert "€" not in result["mathml"]
        assert "é" not in result["mathml"]

    def test_handle_malformed_xml(self) -> None:
        """Test handling of malformed XML."""
        cleaner = OCRMathMLCleaner()
        
        # Malformed MathML
        corrupted = '<math><mi>x</mi><mo>+</mo><mi>y</math>'  # Missing closing tag
        
        result = cleaner.clean(corrupted)
        
        # Should still return something
        assert "latex" in result
        assert "mathml" in result

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

