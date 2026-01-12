"""Service for exporting LaTeX tables to TSV."""
import re
from core.logger import logger

class TableExporter:
    """Service to convert LaTeX tables (tabular/array) to TSV format."""
    
    def to_tsv(self, latex: str) -> str:
        """
        Convert LaTeX tabular or array environment to a TSV string.
        """
        if not latex:
            return ""
            
        try:
            # 1. Extract content between \begin and \end
            body_match = re.search(r'\\begin\{(?:tabular|array)\}(?:\{.*?\})?(.*?)\\end\{(?:tabular|array)\}', latex, re.DOTALL)
            if not body_match:
                # If no explicit environment, try to parse raw content with \\ and &
                if '&' in latex and r'\\' in latex:
                    body = latex
                else:
                    return ""
            else:
                body = body_match.group(1)
            
            # 2. Split into rows by \\
            # Also handle potential line break variations
            rows = re.split(r'\\\\|\\cr', body)
            
            tsv_rows = []
            for row in rows:
                row = row.strip()
                if not row:
                    continue
                
                # 3. Split into columns by &
                # Use regex to handle potential \& escapes
                # This is simple; a more robust one would use a proper parser
                cols = re.split(r'(?<!\\)&', row)
                
                clean_cols = []
                for col in cols:
                    # Clean up LaTeX artifacts in cells
                    c = col.strip()
                    # Remove common formatting
                    c = re.sub(r'\\(?:textbf|textit|text|mathrm)\{(.*?)\}', r'\1', c)
                    # Remove remaining backslashes
                    c = c.replace('\\', '')
                    # Remove curly braces
                    c = c.replace('{', '').replace('}', '')
                    clean_cols.append(c)
                
                tsv_rows.append('\t'.join(clean_cols))
            
            return '\n'.join(tsv_rows)
            
        except Exception as e:
            logger.error(f"Table export to TSV failed: {e}")
            return ""

    def is_table(self, latex: str) -> bool:
        """Check if the LaTeX contains a table environment or structure."""
        if any(env in latex for env in [r'\begin{tabular}', r'\begin{array}']):
            return True
        # Heuristic: multiple & and \\
        if latex.count('&') >= 2 and latex.count(r'\\') >= 1:
            return True
        return False
