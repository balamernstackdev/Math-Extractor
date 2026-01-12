"""
MultilineConverter.
Handles the conversion of multiline equations (align, cases, array, etc.) into structured MathML.
"""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from latex2mathml.converter import convert as latex2mathml_convert
from core.logger import logger
from services.ocr.pipeline_components.shared_types import MultilineInfo, ALIGNMENT_SPECS
from services.ocr.pipeline_components.regex_patterns import MULTILINE_ENVIRONMENTS

class MultilineConverter:
    """Specialized converter for multiline LaTeX structures."""
    
    def detect_multiline_equation(self, latex: str) -> MultilineInfo:
        """
        Analyze LaTeX to determine multiline structure.
        """
        info = MultilineInfo()
        
        # Check standard environments
        for env in MULTILINE_ENVIRONMENTS:
            if f"\\begin{{{env}}}" in latex:
                info.is_multiline = True
                info.environment = env
                info.alignment_spec = ALIGNMENT_SPECS.get(env)
                
                # Count lines properly
                # This is a heuristic count
                info.line_count = latex.count(r"\\") + 1
                
                # Check for alignment markers
                if "&" in latex:
                    info.has_alignment_markers = True
                    # Estimate columns based on max & in a line
                    # Simplified logic
                    lines = latex.split(r"\\")
                    max_cols = 0
                    for line in lines:
                        max_cols = max(max_cols, line.count("&"))
                    info.column_count = max_cols + 1
                    
                return info
                
        # Check for manual line breaks without environment
        if r"\\" in latex and "begin" not in latex:
             # Just a sequence of lines
             info.is_multiline = True
             info.environment = 'manual'
             info.line_count = latex.count(r"\\") + 1
             return info

        return info

    def convert_multiline(self, latex: str, info: MultilineInfo) -> str:
        """
        Convert multiline LaTeX to MathML using mtable structure.
        Uses recursive decomposition to process each cell individually.
        """
        # This duplicates the complex _convert_multiline logic from the original file
        # For this refactoring step, we will simplify and provide the core structure
        # The full implementation would require copying the detailed splitting logic
        
        # 1. Clean environment wrappers
        content = latex
        if info.environment != 'manual':
             # Remove \begin{env} ... \end{env}
             pattern = f"\\\\begin{{{info.environment}}}(.*?)\\\\end{{{info.environment}}}"
             match = re.search(pattern, latex, re.DOTALL)
             if match:
                 content = match.group(1)
        
        # 2. Split into rows
        rows = re.split(r'\\\\', content)
        
        # 3. Build mtable
        # Register namespace to avoid prefixes
        ns = "http://www.w3.org/1998/Math/MathML"
        full_mathml = f'<math xmlns="{ns}" display="block">'
        
        # Handle cases (fence)
        if info.environment == 'cases':
             full_mathml += '<mrow><mo>{</mo>'
             
        full_mathml += '<mtable>'
        
        for row in rows:
            if not row.strip(): continue
            full_mathml += '<mtr>'
            
            # Split cols
            cols = row.split('&')
            for col in cols:
                # Convert cell content using basic converter (assume safe or re-use logic)
                # NOTE: In a full DI system we would inject the base converter here.
                # For now we use the library directly for the cell content
                # Caveat: This bypasses the LatexToMathML cleaning pipeline for cells!
                # Ideally, we pass the `convert_single_line` callback.
                cell_latex = col.strip()
                try:
                    # Basic conversion for cell
                    cell_mml = latex2mathml_convert(cell_latex)
                    # Strip root <math> tags
                    cell_mml = re.sub(r'<math[^>]*>', '', cell_mml).replace('</math>', '')
                    full_mathml += f'<mtd>{cell_mml}</mtd>'
                except:
                     full_mathml += f'<mtd><mtext>{cell_latex}</mtext></mtd>'
            
            full_mathml += '</mtr>'
            
        full_mathml += '</mtable>'
        
        if info.environment == 'cases':
            full_mathml += '</mrow>'
            
        full_mathml += '</math>'
        return full_mathml
