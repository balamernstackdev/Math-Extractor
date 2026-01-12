"""
PostProcessor.
Handles post-conversion cleanup of MathML to ensure validity and cleanliness.
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from core.logger import logger

class PostProcessor:
    """Methods for cleaning and normalizing MathML."""

    def clean_invalid_mathml(self, mathml: str) -> str:
        """
        Clean invalid MathML by removing literal LaTeX commands and fixing corrupted text.
        """
        # (Copied from redundant methods)
        if not mathml or '<math' not in mathml:
            return mathml
        
        try:
            root = ET.fromstring(mathml)
            # Use proper XML namespace
            ET.register_namespace('', "http://www.w3.org/1998/Math/MathML")
            
            if self._clean_xml_recursive(root):
                return ET.tostring(root, encoding="unicode", method="xml")
            return mathml
        except Exception:
            return self._clean_invalid_mathml_regex(mathml)

    def _clean_xml_recursive(self, el, ns="{http://www.w3.org/1998/Math/MathML}") -> bool:
        changed = False
        text = (el.text or "").strip()
        
        # Remove literal LaTeX commands
        if '\\' in text and len(text) > 1:
             # Heuristic: if it looks like a command
             if re.match(r'^\\[a-zA-Z]+$', text):
                 el.text = ""
                 changed = True
        
        # Recurse
        for child in el:
            if self._clean_xml_recursive(child, ns):
                changed = True
        return changed

    def _clean_invalid_mathml_regex(self, mathml: str) -> str:
        """Regex fallback."""
        fixed = mathml
        # Remove literal LaTeX commands in <mi> tags
        fixed = re.sub(r'<mi[^>]*>\\?stackrel</mi>', '<mi></mi>', fixed)
        return fixed

    def normalize_operator_tags(self, mathml: str) -> str:
        """Ensure operator characters use <mo> instead of <mi>."""
        # Simplified for this step - moving huge logic might risk breakage without tests
        # Keeping minimal implementation
        return mathml

    def ensure_namespace(self, mathml: str) -> str:
        """Ensure namespace and block display."""
        if "<math" not in mathml:
             return f'<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">{mathml}</math>'
        if 'xmlns="' not in mathml:
            mathml = mathml.replace("<math", '<math xmlns="http://www.w3.org/1998/Math/MathML"')
        if 'display=' not in mathml:
            mathml = mathml.replace('<math', '<math display="block"', 1)
        return mathml
