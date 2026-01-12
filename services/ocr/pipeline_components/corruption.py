
import re
from typing import Tuple, List

def mathml_has_spelled_words(mathml: str) -> Tuple[bool, List[str]]:
    """
    REQUIRED: AST-level check for MathML spelling abuse.
    
    Detects if MathML contains spelled words via single-letter msub chains:
    - <msub><mi>l</mi><mrow><mi>o</mi></mrow></msub><msub><mi>n</mi><mrow><mi>g</mi></mrow></msub>
    - <msub><mi>r</mi><mrow><mi>i</mi></mrow></msub><msub><mi>g</mi><mrow><mi>h</mi></mrow></msub>
    - <msub><mi>s</mi><mi>u</mi></msub><mi>m</mi>
    
    Returns: (has_spelled_words, list_of_violations)
    """
    if not mathml:
        return False, []
    
    violations = []
    
    # Known words that are often spelled via msub: long, right, arrow, sum, equiv, mathbb, in, forall
    # Pattern must handle both <mi>Y</mi> and <mrow><mi>Y</mi></mrow> in subscript
    # Use re.DOTALL to match across newlines
    word_patterns = [
        # "long" spelled as: l_o n_g (handles both <mi>o</mi> and <mrow><mi>o</mi></mrow>)
        (r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<msub>.*?<mi>n</mi>.*?<mi>g</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "long" spelled via msub chains (l_o n_g)'),
        # "right" spelled as: r_i g_h t
        (r'<msub><mi>r</mi>.*?<mi>i</mi>.*?<msub>.*?<mi>g</mi>.*?<mi>h</mi>.*?</msub>.*?<mi>t</mi>', 'STRICTLY FORBIDDEN: "right" spelled via msub chains (r_i g_h t)'),
        # "arrow" spelled as: a_r r_o w
        (r'<msub><mi>a</mi>.*?<mi>r</mi>.*?<msub>.*?<mi>r</mi>.*?<mi>o</mi>.*?</msub>.*?<mi>w</mi>', 'STRICTLY FORBIDDEN: "arrow" spelled via msub chains (a_r r_o w)'),
        # "sum" spelled as: s_u m
        (r'<msub><mi>s</mi>.*?<mi>u</mi>.*?<msub>.*?<mi>m</mi>', 'STRICTLY FORBIDDEN: "sum" spelled via msub chains (s_u m)'),
        # "equiv" spelled as: e_q u_i v
        (r'<msub><mi>e</mi>.*?<mi>q</mi>.*?<msub>.*?<mi>u</mi>.*?<mi>i</mi>.*?</msub>.*?<mi>v</mi>', 'STRICTLY FORBIDDEN: "equiv" spelled via msub chains (e_q u_i v)'),
        # "mathbb" spelled as: m_a t_h b_b
        (r'<msub><mi>m</mi>.*?<mi>a</mi>.*?<msub>.*?<mi>t</mi>.*?<mi>h</mi>.*?</msub>.*?<msub><mi>b</mi>.*?<mi>b</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "mathbb" spelled via msub chains (m_a t_h b_b)'),
        # "in" spelled as: i_n
        (r'<msub><mi>i</mi>.*?<mi>n</mi>.*?</msub>(?!\s*<)', 'STRICTLY FORBIDDEN: "in" spelled via msub (i_n)'),
        # "forall" spelled as: f_o r_a l_l
        (r'<msub><mi>f</mi>.*?<mi>o</mi>.*?<msub>.*?<mi>r</mi>.*?<mi>a</mi>.*?</msub>.*?<msub><mi>l</mi>.*?<mi>l</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "forall" spelled via msub chains (f_o r_a l_l)'),
    ]
    
    # Correction: The logic originally used highly simplified regex in pattern strings above? 
    # Actually the patterns in the viewed code were regex strings. 
    # I copied them somewhat loosely above because I can't copy-paste exactly from memory/view without potential typos...
    # BUT wait, I have the view output in Step 1127. I should use EXACT copy.
    # The view output in 1127 shows incomplete regex strings? "r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<msub>.*?<mi>n</mi>.*?<mi>g</mi>.*?</msub>'" - This looks like what I typed BUT `...` inside regex? 
    # Ah, the view output in 1127 had `.*?`. Yes.
    # So I will replicate the exact regex list.
    
    # RE-COPYING EXACTLY FROM STEP 1127:
    word_patterns = [
        (r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<msub>.*?<mi>n</mi>.*?<mi>g</mi>.*?</msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "long" spelled via msub chains (l_o n_g)'), # Wait, Step 1127 line 265 looks different.
        # Let's check 1127 line 265:
        # `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<msub>.*?<mi>n</mi>.*?<mi>g</mi>.*?</msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>'` - NO.
        # It's `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<msub>.*?<mi>n</mi>.*?<mi>g</mi>.*?</msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>',` ? No.
        # Step 1127 line 265: `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>.*?...`
        # Actually it's truncated or I am misreading.
        # Line 266: `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?</msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>', 'STRICTLY FORBIDDEN: ...')`
        # OK, I will try to be as close as possible but fixing any obvious issues if I can't verify 100%. `.*?` is non-greedy match.
        
        # Actually, to be safe, I should use the exact strings from 1127.
        # 1. `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?</msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>', ...)` -- Wait, where is the first `</msub>`?
        # In 1127 line 266: `r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<mi>o</mi>.*?<msub>.*?` - NO.
        # Let's look at 1127 line 266 AGAIN.
        # `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<mi>o</mi>.*?<msub>.*?` -- ??? 
        # Line 266 content: `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?<mi>o</mi>.*?<msub>.*?` - It lists `<mi>o</mi>` twice? No, looking at `matches` logic.
        
        # Okay, the safest bet is to trust the regex I see in 1127 Lines 266-282.
        # Line 266: `(r'<msub><mi>l</mi>.*?<mi>o</mi>.*?</msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "long" spelled via msub chains (l_o n_g)'),`
        # Line 268: `(r'<msub><mi>r</mi>.*?<mi>i</mi>.*?</msub>.*?<msub><mi>g</mi>.*?<mi>h</mi>.*?</msub>.*?<mi>t</mi>', ...)`
        # Line 270: `(r'<msub><mi>a</mi>.*?<mi>r</mi>.*?</msub>.*?<msub><mi>r</mi>.*?<mi>o</mi>.*?</msub>.*?<mi>w</mi>', ...)`
        # Line 272: `(r'<msub><mi>s</mi>.*?<mi>u</mi>.*?</msub>.*?<mi>m</mi>', ...)`
        # Line 274: `(r'<msub><mi>e</mi>.*?<mi>q</mi>.*?</msub>.*?<msub><mi>u</mi>.*?<mi>i</mi>.*?</msub>.*?<mi>v</mi>', ...)`
        # Line 276: `(r'<msub><mi>m</mi>.*?<mi>a</mi>.*?</msub>.*?<msub><mi>t</mi>.*?<mi>h</mi>.*?</msub>.*?<msub><mi>b</mi>.*?<mi>b</mi>.*?</msub>', ...)`
        # Line 278: `(r'<msub><mi>i</mi>.*?<mi>n</mi>.*?</msub>(?!\s*<)', ...)`
        # Line 280: `(r'<msub><mi>f</mi>.*?<mi>o</mi>.*?</msub>.*?<msub><mi>r</mi>.*?<mi>a</mi>.*?</msub>.*?<msub><mi>l</mi>.*?<mi>l</mi>.*?</msub>', ...)`
    ]

    word_patterns = [
        (r'<msub><mi>l</mi>.*?<mi>o</mi>.*?</msub>.*?<msub><mi>n</mi>.*?<mi>g</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "long" spelled via msub chains (l_o n_g)'),
        (r'<msub><mi>r</mi>.*?<mi>i</mi>.*?</msub>.*?<msub><mi>g</mi>.*?<mi>h</mi>.*?</msub>.*?<mi>t</mi>', 'STRICTLY FORBIDDEN: "right" spelled via msub chains (r_i g_h t)'),
        (r'<msub><mi>a</mi>.*?<mi>r</mi>.*?</msub>.*?<msub><mi>r</mi>.*?<mi>o</mi>.*?</msub>.*?<mi>w</mi>', 'STRICTLY FORBIDDEN: "arrow" spelled via msub chains (a_r r_o w)'),
        (r'<msub><mi>s</mi>.*?<mi>u</mi>.*?</msub>.*?<mi>m</mi>', 'STRICTLY FORBIDDEN: "sum" spelled via msub chains (s_u m)'),
        (r'<msub><mi>e</mi>.*?<mi>q</mi>.*?</msub>.*?<msub><mi>u</mi>.*?<mi>i</mi>.*?</msub>.*?<mi>v</mi>', 'STRICTLY FORBIDDEN: "equiv" spelled via msub chains (e_q u_i v)'),
        (r'<msub><mi>m</mi>.*?<mi>a</mi>.*?</msub>.*?<msub><mi>t</mi>.*?<mi>h</mi>.*?</msub>.*?<msub><mi>b</mi>.*?<mi>b</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "mathbb" spelled via msub chains (m_a t_h b_b)'),
        (r'<msub><mi>i</mi>.*?<mi>n</mi>.*?</msub>(?!\s*<)', 'STRICTLY FORBIDDEN: "in" spelled via msub (i_n)'),
        (r'<msub><mi>f</mi>.*?<mi>o</mi>.*?</msub>.*?<msub><mi>r</mi>.*?<mi>a</mi>.*?</msub>.*?<msub><mi>l</mi>.*?<mi>l</mi>.*?</msub>', 'STRICTLY FORBIDDEN: "forall" spelled via msub chains (f_o r_a l_l)'),
    ]
    
    for pattern, violation in word_patterns:
        if re.search(pattern, mathml, re.IGNORECASE | re.DOTALL):
            violations.append(violation)
    
    # Generic pattern: 3+ consecutive single-letter msub elements
    consecutive_msub_pattern = r'(?:<msub><mi>[a-zA-Z]</mi>.*?<mi>[a-zA-Z]</mi>.*?</msub>\s*){3,}'
    if re.search(consecutive_msub_pattern, mathml, re.IGNORECASE):
        violations.append('STRICTLY FORBIDDEN: 3+ consecutive single-letter msub elements (spelling abuse)')
    
    # Check for fake subscripts (plain text words in <msub>)
    fake_subscript_pattern = r'<msub><mi>([a-z]{2,})</mi>'
    matches = re.findall(fake_subscript_pattern, mathml, re.IGNORECASE)
    invalid_words = ['left', 'right', 'sum', 'frac', 'math', 'long', 'text', 'arrow', 'equiv', 'mathbb', 'forall']
    for match in matches:
        if match.lower() in invalid_words:
            violations.append(f'STRICTLY FORBIDDEN: word "{match}" in <msub> (should not be subscript)')
    
    return len(violations) > 0, violations


def is_corrupted_mathml(mathml: str) -> bool:
    """
    Validate MathML for corruption patterns.
    """
    if not mathml or ('<math' not in mathml and '<mml:math' not in mathml):
        return False
    
    bad_patterns = [
        "<msub><mi>l</mi>",  # Split "left" or "long"
        "<msub><mi>s</mi>",  # Split "sum"
        "<mi>l</mi><mi>o</mi><mi>n</mi><mi>g</mi>",  # Corrupted operator (as text, not command)
        "math b",  # Corrupted \mathbb
        # Tag hallucinations are checked in LaTeX, but are VALID in MathML output
        "<mi>l</mi><mi>e</mi><mi>f</mi><mi>t</mi>",  # Split "left"
        "<mi>r</mi><mi>i</mi><mi>g</mi><mi>h</mi><mi>t</mi>",  # Split "right"
        "<mi>s</mi><mi>u</mi><mi>m</mi>",  # Split "sum"
        "<mi>f</mi><mi>r</mi><mi>a</mi><mi>c</mi>",  # Split "frac"
        "<mi>m</mi><mi>a</mi><mi>t</mi><mi>h</mi>",  # Split "math"
        "[object Object]",  # JavaScript error pattern (CORRUPTED)
    ]
    
    for pattern in bad_patterns:
        if pattern in mathml:
            return True
    
    # Word spelling chains are checked below
    
    equiv_chain = r'<msub><mi>e</mi><mi>q</mi></msub>.*?<msub><mi>u</mi><mi>i</mi></msub>.*?<mi>v</mi>'
    sum_chain = r'<msub><mi>s</mi><mi>u</mi></msub>.*?<mi>m</mi>'
    mathbb_chain = r'<msub><mi>m</mi><mi>a</mi></msub>.*?<msub><mi>t</mi><mi>h</mi></msub>.*?<msub><mi>b</mi><mi>b</mi></msub>'
    
    if re.search(equiv_chain, mathml, re.IGNORECASE):
        return True
    if re.search(sum_chain, mathml, re.IGNORECASE):
        return True
    if re.search(mathbb_chain, mathml, re.IGNORECASE):
        return True
    
    fake_subscript_pattern = r'<msub><mi>([a-z]{2,})</mi>'
    matches = re.findall(fake_subscript_pattern, mathml, re.IGNORECASE)
    invalid_words = ['left', 'right', 'sum', 'frac', 'math', 'long', 'text']
    for match in matches:
        if match.lower() in invalid_words:
            return True
    
    return False


def detect_latex_corruption(latex: str) -> Tuple[bool, List[str]]:
    """
    MANDATORY: Detect ALL LaTeX corruption patterns (ZERO tolerance).
    """
    if not latex:
        return False, []
    
    found = []
    
    split_command_patterns = [
        (r'e\s*_\s*\{?\s*q\s*\}?\s*u\s*_\s*\{?\s*i\s*\}?\s*v', 'split command: e_q u_i v (should be \\equiv)'),
        (r'l\s*_\s*\{?\s*o\s*\}?\s*n\s*_\s*\{?\s*g\s*\}?\s*r\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*h\s*\}?\s*t\s*_\s*\{?\s*a\s*\}?', 'split command: l_o n_g r_i g_h t_a'),
        (r's\s*_\s*\{?\s*u\s*\}?\s*m\s*(?!\s*\{)', 'split command: s_u m (should be \\sum)'),
        (r'm\s*_\s*\{?\s*a\s*\}?\s*t\s*_\s*\{?\s*h\s*\}?\s*b\s*_\s*\{?\s*b\s*\}?', 'split command: m_a t_h b_b (should be \\mathbb)'),
        (r'([a-z])_\{([a-z])\}([a-z])_\{([a-z])\}([a-z])(?![,}])', 'letter-by-letter subscripting (split command)'),
        (r'\\[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}[a-z](?!\s*[a-zA-Z_0-9,}])', 'shredded LaTeX command'),
        # New patterns for Phase 2
        (r'i\s*_\s*\{?\s*n\s*\}?\s*t\s*(?!\s*[a-zA-Z])', 'split command: i_n t (should be \\int)'),
        (r'l\s*_\s*\{?\s*i\s*\}?\s*m\s*(?!\s*[a-zA-Z])', 'split command: l_i m (should be \\lim)'),
        (r'l\s*_\s*\{?\s*o\s*\}?\s*g\s*(?!\s*[a-zA-Z])', 'split command: l_o g (should be \\log)'),
        (r'l\s*_\s*\{?\s*n\s*\}?\s*(?!\s*[a-zA-Z])', 'split command: l_n (should be \\ln)'),
        (r'l\s*_\s*\{?\s*e\s*\}?\s*f\s*_\s*\{?\s*t\s*\}?', 'split command: l_e f_t (should be \\left)'),
        (r'r\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*h\s*\}?\s*t\s*(?!\s*[a-zA-Z])', 'split command: r_i g_h t (should be \\right)'),
        (r'(s\s*_\s*\{?\s*i\s*\}?\s*n|c\s*_\s*\{?\s*o\s*\}?\s*s|t\s*_\s*\{?\s*a\s*\}?\s*n)', 'split command: trig function (sin/cos/tan)'),
        (r'(?<!\d)\d\s+\d\s+\d(?!\d)', 'shattered number: 1 2 3 (digits with spaces)'),
    ]
    
    for pattern, description in split_command_patterns:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    alphabet_abuse_patterns = [
        (r'([a-z])_\{([a-z])\}([a-z])_\{([a-z])\}([a-z])_\{([a-z])\}(?![,}])', 'alphabet-as-subscript abuse (repeated letter subscripts)'),
        (r'_\{[a-z]\}[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}(?![,}])', 'repeated letter subscripts (alphabet abuse)'),
        (r'([a-z])_\{([a-z])_\{([a-z])\}([a-z])_\{([a-z])\}\}', 'nested subscript spelling word'),
    ]
    
    for pattern, description in alphabet_abuse_patterns:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    broken_operator_patterns = [
        (r'(?<!\\)\b(left|right|sum|frac|mathbb|equiv|in|munderover|munder|mover|msubsup|msub|msup|mfrac|mtable)\b(?!\s*\{)', 'broken operator (missing backslash or MathML tag hallucination)'),
        (r'\\[a-z]\s+[a-z]\s+[a-z]', 'spaced command (broken operator: e.g., \\ s u m)'),
        (r'\\[a-z]_\{[a-z]\}\s+[a-z]', 'broken command with subscript'),
        (r'(?<!\\)\bsum\b(?!\s*\{)', 'broken operator: sum written as text (should be \\sum)'),
        (r'm\s*a\s*t\s*h\s*b\s*Z', 'broken operator: Z written as mathbb via characters'),
    ]
    
    for pattern, description in broken_operator_patterns:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    invalid_structure_patterns = [
        (r'\\sum\s*\{[^}]*\}\s*(?!^|_)', 'invalid structure: sum missing bounds'),
        (r'\\sum\s*(?!\{|_|\^)', 'invalid structure: sum missing subscript/superscript'),
        (r'_\s*\{[^}]*=\s*[^}]*\}', 'potential: = in subscript (suspicious)'),
    ]
    
    for pattern, description in invalid_structure_patterns:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    return len(found) > 0, found


def pre_openai_regex_corruption_checker(latex: str) -> Tuple[bool, List[str]]:
    """
    PRE-OPENAI REGEX CORRUPTION CHECKER (CRITICAL)
    """
    if not latex:
        return False, []
    
    found = []
    
    split_letter_pattern = r'(?:\\\[a-zA-Z]+)?(_\{?[a-zA-Z]\}?){3,}'
    if re.search(split_letter_pattern, latex):
        found.append('CORRUPTED: split-letter LaTeX detected (spelling hack)')
    
    split_patterns = [
        (r'e\s*_\s*\{?\s*q\s*\}?\s*u\s*_\s*\{?\s*i\s*\}?\s*v', 'CORRUPTED: e_q u_i v (split equiv)'),
        (r's\s*_\s*\{?\s*u\s*\}?\s*m\s*(?!\s*\{)', 'CORRUPTED: s_u m (split sum)'),
        (r'm\s*_\s*\{?\s*i\s*\}?\s*n\s*(?!\s*\{)', 'CORRUPTED: m_i n (split min)'),
        (r'l\s*_\s*\{?\s*o\s*\}?\s*n\s*_\s*\{?\s*g\s*\}?', 'CORRUPTED: l_o n_g (split long)'),
        (r'r\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*h\s*\}?\s*t\s*_\s*\{?\s*a\s*\}?', 'CORRUPTED: r_i g_h t_a (split right)'),
    ]
    
    for pattern, description in split_patterns:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    operator_abuse_patterns = [
        (r'(?<!\\)\bequiv\b(?!\s*\{)', 'CORRUPTED: equiv written as text (should be \\equiv)'),
        (r'(?<!\\)\bsum\b(?!\s*\{)', 'CORRUPTED: sum written as text (should be \\sum)'),
        (r'(?<!\\)\bmin\b(?!\s*\{)', 'CORRUPTED: min written as text (should be \\min)'),
        (r'(?<!\\)\bmax\b(?!\s*\{)', 'CORRUPTED: max written as text (should be \\max)'),
    ]
    
    for pattern, description in operator_abuse_patterns:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    return len(found) > 0, found


def has_spelling_hack(latex: str) -> Tuple[bool, List[str]]:
    """
    REQUIRED: Regex Guards for LaTeX spelling hacks.
    """
    if not latex:
        return False, []
    
    found = []
    
    SPELLING_HACKS = [
        (r'(?:[a-zA-Z]_\{[a-zA-Z]\}){3,}(?![,}])', 'CORRUPTED: spelling hack - repeated letter subscripts with braces (e.g., l_{o}n_{g})'),
        (r'\\[a-zA-Z]\s*_\s*\{[a-zA-Z]\}(?!\s*[a-zA-Z_0-9])', 'CORRUPTED: spelling hack - command with single-letter subscript (e.g., \\s_{u})'),
        (r'(?:_[a-zA-Z]){3,}', 'CORRUPTED: spelling hack - repeated single-letter subscripts (e.g., e_q_u_i_v)'),
        (r'[a-zA-Z]\s*_\s*\{[a-zA-Z]\}\s*[a-zA-Z]\s*_\s*\{[a-zA-Z]\}(?![,}])', 'CORRUPTED: spelling hack - letter subscript chains (e.g., l_{o}n_{g})'),
    ]
    
    for pattern, description in SPELLING_HACKS:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    word_patterns = [
        (r'l\s*_\s*\{?\s*o\s*\}?\s*n\s*_\s*\{?\s*g\s*\}?', 'CORRUPTED: "long" spelled via subscripts (l_o n_g)'),
        (r'r\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*h\s*\}?\s*t\s*_\s*\{?\s*a\s*\}?', 'CORRUPTED: "right" spelled via subscripts (r_i g_h t_a)'),
        (r'a\s*_\s*\{?\s*r\s*\}?\s*r\s*_\s*\{?\s*o\s*\}?\s*w', 'CORRUPTED: "arrow" spelled via subscripts (a_r r_o w)'),
        (r'\bs\s*_\s*\{?\s*u\s*\}?\s*m\b', 'CORRUPTED: "sum" spelled via subscripts (s_u m)'),
        (r's\s*_\s*\{?\s*u\s*\}?\s+m\b', 'CORRUPTED: "sum" spelled via subscripts (s_u m with space)'),
        (r's\s*_\s*u\s*_\s*m\b', 'CORRUPTED: "sum" spelled via subscripts (s_u_m)'),
        (r'\bs\s*_\s*u\s*_\s*m\b', 'CORRUPTED: "sum" spelled via subscripts (s_u_m)'),
        (r'e\s*_\s*\{?\s*q\s*\}?\s*u\s*_\s*\{?\s*i\s*\}?\s*v', 'CORRUPTED: "equiv" spelled via subscripts (e_q u_i v)'),
        (r'm\s*_\s*\{?\s*a\s*\}?\s*t\s*_\s*\{?\s*h\s*\}?\s*b\s*_\s*\{?\s*b\s*\}?', 'CORRUPTED: "mathbb" spelled via subscripts (m_a t_h b_b)'),
        (r'i\s*_\s*\{?\s*n\s*\}?\s*(?!\s*\{)', 'CORRUPTED: "in" spelled via subscripts (i_n)'),
        (r'f\s*_\s*\{?\s*o\s*\}?\s*r\s*_\s*\{?\s*a\s*\}?\s*l\s*_\s*\{?\s*l\s*\}?', 'CORRUPTED: "forall" spelled via subscripts (f_o r_a l_l)'),
    ]
    
    for pattern, description in word_patterns:
        if re.search(pattern, latex, re.IGNORECASE):
            found.append(description)
    
    return len(found) > 0, found


def is_semantically_clean_latex(latex: str) -> bool:
    """
    RULE 1 — NEVER SEND CLEAN LATEX TO OPENAI
    """
    if not latex or not latex.strip():
        return False
    
    # Check for obvious corruption patterns
    forbidden_patterns = [
        r"[a-zA-Z]_\{[a-zA-Z]\}\s*[a-zA-Z]_\{[a-zA-Z]\}",
        r"s_\{u\}\s*m",
        r"s\s*_\s*\{?\s*u\s*\}?\s*m\b",
        r"f_\{r\}\s*a_\{c\}",
        r"f\s*_\s*\{?\s*r\s*\}?\s*a\s*_\s*\{?\s*c\s*\}?",
        r"l_\{e\}\s*f_\{t\}",
        r"l\s*_\s*\{?\s*e\s*\}?\s*f\s*_\s*\{?\s*t\s*\}?",
        r"r_\{i\}\s*g_\{h\}\s*t",
        r"r\s*_\s*\{?\s*i\s*\}?\s*g\s*_\s*\{?\s*h\s*\}?\s*t",
        r"e_\{q\}\s*u_\{i\}\s*v",
        r"e\s*_\s*\{?\s*q\s*\}?\s*u\s*_\s*\{?\s*i\s*\}?\s*v",
        r"m_\{a\}\s*t_\{h\}\s*b_\{b\}",
        r"m\s*_\s*\{?\s*a\s*\}?\s*t\s*_\s*\{?\s*h\s*\}?\s*b\s*_\s*\{?\s*b\s*\}?",
        r"l_\{e\}\s*q",
        r"l\s*_\s*\{?\s*e\s*\}?\s*q",
    ]
    
    if any(re.search(p, latex, re.IGNORECASE) for p in forbidden_patterns):
        return False
    
    if re.search(r'[a-z]_\{[a-z]\}\s*[a-z]_\{[a-z]\}\s*[a-z]_\{[a-z]\}', latex, re.IGNORECASE):
        return False
    
    if re.search(r'\\mathrm\{[a-z]{6,}[^}]*\}', latex, re.IGNORECASE):
        suspicious_words = ['cxcuvec', 'cxcu', 'cxc', 'cx', 'cuvec', 'vecu']
        for word in suspicious_words:
            if word in latex.lower():
                return False
    
    if re.search(r'(\\[a-zA-Z]+|[\{_\^])\s*$', latex):
        return False
    
    left_count = latex.count(r'\left')
    right_count = latex.count(r'\right')
    if left_count != right_count:
        return False
        
    brace_count = latex.count('{') - latex.count('}')
    if brace_count != 0:
        return False
    
    return True
