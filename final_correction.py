import os

path = r'd:\test-r&d\mathpix_clone\tests\verify_semantic_ast.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Fix Double Integral check (D is a subscript, so it's munder or msub)
# Actually, for large operators, we use munder.
old_double_int = '"check": lambda ast, mml: "munderover" in mml and "∬" in mml'
# Allow munder too.
new_double_int = '"check": lambda ast, mml: ("munderover" in mml or "munder" in mml) and "\\u222c" in mml'
text = text.replace(old_double_int, new_double_int)

# 2. Fix Derivative check
# The latex is \frac{\mathrm{d}}{\mathrm{d}x} f(x)
# The check is: "check": lambda ast, mml: "mathrm" in mml and "d" in mml
# Serialization for mathvariant="mathrm" produced <mstyle mathvariant="mathrm"> or <mi mathvariant="mathrm"> or <mtext variant="mathrm">?
# Let's check serializer for 'text' node.
# It returns <mtext>...
# Wait, I'll update the check for 'mathvariant="mathrm"' or just 'mathrm' in mml.
# Actually, the check "mathrm" in mml should work if <mtext variant="mathrm"> or similar is there.

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

# 3. Final Fix for LaTeXParser Text Styles
parser_path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
# I'll use a simpler search-replace for the text styles block
with open(parser_path, 'r', encoding='utf-8') as f:
    parser_text = f.read()

# Fix the redundant escapes in Text/Styles block
old_list = '["\\\\text", "\\\\mbox", "\\\\mathrm", "\\\\mathbf", "\\\\mathcal", "\\\\mathbb", "\\\\operatorname"]'
new_list = '[r"\\text", r"\\mbox", r"\\mathrm", r"\\mathbf", r"\\mathcal", r"\\mathbb", r"\\operatorname"]'
parser_text = parser_text.replace(old_list, new_list)

with open(parser_path, 'w', encoding='utf-8') as f:
    f.write(parser_text)
