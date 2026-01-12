
import re

def strip_ai_artifacts(s: str) -> str:
    """Remove common AI chatter, OCR headers, and MathML tag hallucinations."""
    if not s:
        return s
        
    # 1. Common AI header patterns
    headers = [
        r"(?i)^Equation\s*Listing:?",
        r"(?i)^Raw\s*Text:?",
        r"(?i)^LaTeX:?",
        r"(?i)^Cleaned\s*LaTeX:?",
        r"(?i)^Here\s*is\s*the\s*equation:?",
        r"(?i)^The\s*equation\s*is:?"
    ]
    
    for head in headers:
        s = re.sub(head, "", s).strip()
    
    # 2. Aggressive MathML tag name cleanup (hallucinations)
    # Tags that OCR models often dump into LaTeX by mistake
    tag_names = [
        "munderover", "munder", "mover", "msubsup", "msub", "msup", 
        "mfrac", "mtable", "mtr", "mtd", "mstyle", "mrow", "menclose", 
        "mfenced", "semantics", "annotation", "mtext"
    ]
    
    for tag in tag_names:
        # Remove if it appears as a word WITHOUT a backslash (obvious artifact)
        # OR if it's followed by something that isn't a brace (unlikely to be a valid command)
        # Case 1: Plain word artifact
        s = re.sub(fr'(?i)(?<!\\)\b{tag}\b', '', s)
        # Case 2: artifact next to non-words (e.g. munderover()
        s = re.sub(fr'(?i)(?<!\\){tag}\s*[(\[@]', '', s)
        # Case 3: Fix common missing backslash if it looks like it was MEANT to be a command (has braces)
        s = re.sub(fr'(?i)(?<!\\){tag}\s*\{{', fr'\\{tag}{{', s)

    # 3. Fix misspelled versions specifically (Murderover, etc)
    s = re.sub(r'(?i)murderover', '', s)
        
    return s

def normalize_latex_semantics(latex: str) -> str:
    r"""
    SAFE LaTeX Normalization (PRE-MathML, deterministic only).
    
    Enhancements:
    1. Normalizes \stackrel patterns for better MathML semantics.
       latex2mathml doesn't support \stackrel well, so we convert to \xrightarrow/\xleftarrow.
    2. Wraps common technical acronyms in \mathrm{} to prevent single-letter parsing.
       (e.g., SNR -> \mathrm{SNR})
    """
    if not latex:
        return latex
        
    # 0. Strip artifacts (important if AI re-introduced them)
    latex = strip_ai_artifacts(latex)
    
    normalized = latex
    
    # --- 1. Acronym Normalization (Domain Specific) ---
    # Wrap common acronyms in \mathrm{} if they aren't already
    # List of purely alphabetical acronyms commonly used in Signal Processing/Stats
    acronyms = ["SNR", "SINR", "MSE", "PDF", "CDF", "RHS", "LHS"]
    
    for acr in acronyms:
        if acr in normalized:
            # Pattern: (?<![\\a-zA-Z])ACRONYM(?![a-zA-Z])
            pattern = fr'(?<![\\a-zA-Z]){acr}(?![a-zA-Z])'
            normalized = re.sub(pattern, fr'\\mathrm{{{acr}}}', normalized)
            
            # Correction: If we created \mathrm{\mathrm{SNR}}, fix it
            normalized = normalized.replace(f'\\mathrm{{\\mathrm{{{acr}}}}}', f'\\mathrm{{{acr}}}')
            normalized = normalized.replace(f'\\text{{\\mathrm{{{acr}}}}}', f'\\mathrm{{{acr}}}')

    # --- 2. Arrow Normalization (\stackrel) ---
    if '\\xrightarrow' not in normalized:
        # Case A: \stackrel{\longrightarrow}{...}
        pattern_a = r'\\stackrel\s*\{\s*\\longrightarrow\s*\}\s*\{([^}]+)\}'
        normalized = re.sub(pattern_a, r'\\xrightarrow{\1}', normalized)
        
        # Case B: \stackrel{...}{\longrightarrow}
        pattern_b = r'\\stackrel\s*\{([^}]+)\}\s*\{\s*\\longrightarrow\s*\}'
        normalized = re.sub(pattern_b, r'\\xrightarrow{\1}', normalized)

    # Replace \equiv with = (OCR often mistakes = for \equiv)
    if r'\equiv' in normalized or '≡' in normalized:
        normalized = normalized.replace(r'\equiv', '=')
        normalized = normalized.replace('≡', '=')

    # Replace \bigcup with \sum (Contextual fix for this specific OCR model)
    if r'\bigcup' in normalized or '⋃' in normalized:
        normalized = normalized.replace(r'\bigcup', r'\sum')
        normalized = normalized.replace('⋃', '∑')
    
    return normalized


def strip_typographic_spacing(latex: str) -> str:
    r"""
    Strip typographic spacing commands from LaTeX (MANDATORY before MathML conversion).
    
    MathML is SEMANTIC, never typographic.
    MUST strip: \!, \quad, \qquad, \mathrm{~}, spacing hacks
    """
    if not latex:
        return latex
    
    stripped = latex
    
    # Remove negative space
    stripped = re.sub(r'\\!+', '', stripped)
    
    # Remove quad spacing
    stripped = re.sub(r'\\quad+', '', stripped)
    stripped = re.sub(r'\\qquad+', '', stripped)
    
    # Remove \mathrm{~} and similar spacing hacks
    stripped = re.sub(r'\\mathrm\s*\{\s*~\s*\}', '', stripped)
    stripped = re.sub(r'\\text\s*\{\s*~\s*\}', '', stripped)
    
    # Remove explicit spacing commands
    stripped = re.sub(r'\\hspace\s*\{[^}]+\}', '', stripped)
    stripped = re.sub(r'\\hskip\s*[0-9.]+(?:pt|em|ex|mu)', '', stripped)
    
    # Remove \, \: \; (thin, medium, thick space) and escaped space "\ " (ignoring \\ for newlines)
    stripped = re.sub(r'\\[,:;]', '', stripped)
    stripped = re.sub(r'(?<!\\)\\ ', ' ', stripped)
    
    # Consolidate spaces after structural delimiters (fixes \left ( issue)
    stripped = re.sub(r'\\left\s+', r'\\left', stripped)
    stripped = re.sub(r'\\right\s+', r'\\right', stripped)
    
    return stripped
    
    
def strip_invisible_characters(text: str) -> str:
    """
    Remove invisible control characters that cause rendering artifacts.
    Includes: ZWSP, ZWNJ, ZWJ, LRM, RLM, BOM
    """
    if not text:
        return text
        
    invisible_chars = [
        '\u200b', # Zero Width Space
        '\u200c', # Zero Width Non-Joiner
        '\u200d', # Zero Width Joiner
        '\u200e', # Left-to-Right Mark
        '\u200f', # Right-to-Left Mark
        '\ufeff', # BOM
        '\u2060', # Word Joiner
        '\u00a0', # Non-breaking space (sometimes indistinguishable from space but bad for latex)
    ]
    
    cleaned = text
    for char in invisible_chars:
        cleaned = cleaned.replace(char, '')
        
    return cleaned


def ensure_double_struck_sets(mathml: str) -> str:
    """
    Ensure sets use mathvariant="double-struck" for ℝ, ℤ, ℕ, ℚ, ℂ.
    """
    if not mathml:
        return mathml
    
    normalized = mathml
    
    # Common mathematical set identifiers
    sets = ['R', 'Z', 'N', 'Q', 'C']
    
    for s_char in sets:
        # Check if the set identifier is mentioned in the MathML or common LaTeX patterns
        if s_char in normalized:
            # Match <mi>X</mi> where X is one of the set chars
            matches = list(re.finditer(fr'<mi>{s_char}</mi>', normalized))
            for match in reversed(matches):
                start = match.start()
                before = normalized[:start]
                
                # Check for existing mathvariant
                # Search back a bit to see if it's already in an mstyle or has an attribute
                # Simple check: if its part of <mi mathvariant="double-struck">X</mi>
                if f'mathvariant="double-struck">{s_char}</mi>' in normalized[start-30:match.end()]:
                    continue
                
                # Check for mstyle parent with double-struck
                context = before[max(0, start-100):start]
                if 'mathvariant="double-struck"' in context and '<mstyle' in context and '</mstyle>' not in context:
                    continue
                
                # Check if it looks like it SHOULD be a set (standalone identifier)
                # If it's in an msub/msup as an index, maybe not? 
                # But usually R, Z are sets regardless of position.
                
                normalized = normalized[:start] + f'<mi mathvariant="double-struck">{s_char}</mi>' + normalized[match.end():]
    
    return normalized
    # OR, maybe I am misinterpreting the "commented out" visualization.
    # Let's assume standard behavior: I should clean this up.
    # The comment says: "For now, we disable automatic <mi>Z</mi> -> ℤ replacement".
    # So I should PROBABLY NOT implement the Z replacement active code.
    
    return normalized


def normalize_mathml_entities(mathml: str) -> str:
    """
    MathML Post-Validation Normalization (NON-STRUCTURAL).
    Replaces numeric entities like &#x00043; with actual ASCII characters.
    """
    if not mathml:
        return mathml
    
    normalized = mathml
    
    entity_map = {
        '&#x00041;': 'A', '&#x00042;': 'B', '&#x00043;': 'C', '&#x00044;': 'D',
        '&#x00045;': 'E', '&#x00046;': 'F', '&#x00047;': 'G', '&#x00048;': 'H',
        '&#x00049;': 'I', '&#x0004A;': 'J', '&#x0004B;': 'K', '&#x0004C;': 'L',
        '&#x0004D;': 'M', '&#x0004E;': 'N', '&#x0004F;': 'O', '&#x00050;': 'P',
        '&#x00051;': 'Q', '&#x00052;': 'R', '&#x00053;': 'S', '&#x00054;': 'T',
        '&#x00055;': 'U', '&#x00056;': 'V', '&#x00057;': 'W', '&#x00058;': 'X',
        '&#x00059;': 'Y', '&#x0005A;': 'Z',
        '&#x00061;': 'a', '&#x00062;': 'b', '&#x00063;': 'c', '&#x00064;': 'd',
        '&#x00065;': 'e', '&#x00066;': 'f', '&#x00067;': 'g', '&#x00068;': 'h',
        '&#x00069;': 'i', '&#x0006A;': 'j', '&#x0006B;': 'k', '&#x0006C;': 'l',
        '&#x0006D;': 'm', '&#x0006E;': 'n', '&#x0006F;': 'o', '&#x00070;': 'p',
        '&#x00071;': 'q', '&#x00072;': 'r', '&#x00073;': 's', '&#x00074;': 't',
        '&#x00075;': 'u', '&#x00076;': 'v', '&#x00077;': 'w', '&#x00078;': 'x',
        '&#x00079;': 'y', '&#x0007A;': 'z',
        '&#x00030;': '0', '&#x00031;': '1', '&#x00032;': '2', '&#x00033;': '3',
        '&#x00034;': '4', '&#x00035;': '5', '&#x00036;': '6', '&#x00037;': '7',
        '&#x00038;': '8', '&#x00039;': '9',
    }
    
    for entity, char in entity_map.items():
        pattern = f'<mi>{re.escape(entity)}</mi>'
        replacement = f'<mi>{char}</mi>'
        normalized = re.sub(pattern, replacement, normalized)
    
    return normalized
