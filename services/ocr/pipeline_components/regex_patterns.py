"""
Shared regex patterns for OCR processing.
Centralizes all regex definitions to avoid duplication and improve maintainability.
"""
import re

# ==============================================================================
# CORRUPTION DETECTION PATTERNS
# ==============================================================================

# Shredded text patterns (e.g. l e f t)
SHREDDED_PATTERNS = [
    r"<mi>\\?[lmr]</mi>\s*<mi>\\?[aei]</mi>\s*<mi>\\?[fgh]</mi>\s*<mi>\\?[t]</mi>",  # left, right
    r"<mi>\\?[fs]</mi>\s*<mi>\\?[ru]</mi>\s*<mi>\\?[am]</mi>\s*<mi>\\?[cm]</mi>",  # frac, sum
    r"<mi>\\?[mb]</mi>\s*<mi>\\?[ai]</mi>\s*<mi>\\?[tg]</mi>\s*<mi>\\?[hc]</mi>",  # math, big
    r"<mi>\\?[ne]</mi>\s*<mi>\\?[eq]</mi>",  # ne, eq
    r"<mi>\\?[ld]</mi>\s*<mi>\\?[do]</mi>\s*<mi>\\?[ot]</mi>\s*<mi>\\?[ts]</mi>",  # ldots, dots
    r"<mi>\\?[bi]</mi>\s*<mi>\\?[ig]</mi>\s*<mi>\\?[gc]</mi>\s*<mi>\\?[cu]</mi>\s*<mi>\\?[up]</mi>",  # bigcup
    r"<mi>\\?[un]</mi>\s*<mi>\\?[nd]</mi>\s*<mi>\\?[de]</mi>\s*<mi>\\?[er]</mi>\s*<mi>\\?[rl]</mi>\s*<mi>\\?[li]</mi>\s*<mi>\\?[in]</mi>\s*<mi>\\?[ne]</mi>",  # underline
]

# Common corrupted LaTeX patterns
CORRUPTED_LATEX = [
    r'\\mathrm\s*\{\s*\\?[a-z]\s*\}\s*\\mathrm',  # Split mathrms
    r'\|\s*\\mathrm',  # Pipe corruption
]

# ==============================================================================
# NORMALIZATION PATTERNS
# ==============================================================================

# Unsupported commands mapping (Command -> Replacement)
UNSUPPORTED_COMMANDS = {
    r'\\stackrel': r'\\overset',
    r'\\mbox': r'\\text',
    r'\\boldsymbol': r'\\mathbf',
    r'\\bm': r'\\mathbf',
    r'\\textnormal': r'\\mathrm',
    r'\\textrm': r'\\mathrm',
}

# Spacing commands to remove
SPACING_COMMANDS = [r'\,', r'\;', r'\:', r'\!', r'\quad', r'\qquad']

# ==============================================================================
# STRUCTURE PATTERNS
# ==============================================================================

# Multiline environments
MULTILINE_ENVIRONMENTS = [
    'align', 'aligned', 'gather', 'gathered', 'eqnarray',
    'split', 'multline', 'cases', 'array', 'matrix', 'pmatrix',
    'bmatrix', 'vmatrix', 'Bmatrix', 'Vmatrix', 'tabular'
]

# Delimiters
DELIMITER_PAIRS = [
    (r'(?<!\\)\{', r'(?<!\\)\}'),  # { }
    (r'\\\{', r'\\\}'),            # \{ \}
    (r'\(', r'\)'),                # ( )
    (r'\[', r'\]'),                # [ ]
    (r'\\left\(', r'\\right\)'),   # \left( \right)
    (r'\\left\[', r'\\right\]'),   # \left[ \right]
    (r'\\left\\{', r'\\right\\}'), # \left\{ \right\}
    (r'\\left\|', r'\\right\|'),   # \left| \right|
    (r'\\langle', r'\\rangle'),    # \langle \rangle
]
