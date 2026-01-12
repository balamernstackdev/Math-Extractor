import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Find all occurrences of r'\n at the start of a line (which means it was broken)
import re
# Look for literal \n in strings that are broken across lines
# Actually, let's just look for '\n' followed by some text that looks like a latex command
# but without the backslash in front of it in the same string.
pass
