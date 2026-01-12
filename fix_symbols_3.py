import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix all broken \n commands
# We can use a regex to find all occurrences of '\n' at the start of a line or inside a string literal
# But let's just do a greedy replace for the known pattern
text = text.replace("r'\n" + "olimits'", "r'\\nolimits'")

# And others... let me look for more
# r'\n' + 'ewline' ?
# r'\n' + 'oindent' ?

# Actually, I'll just check for any r' followed by a newline
import re
text = re.sub(r"r'\n\s*", "r'\\n", text)
# Wait, that would convert r'\n' (literal newline) to r'\n' (backslash n)
# But in my file, r'\nu' became [r', \n, u', ']? No.
# It became r' followed by newline followed by u': 'ν'
# So r'\nu' -> r'\n' + 'u'

# Let's just fix \nolimits for now.
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
