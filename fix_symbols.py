import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the split-back-to-join errors
text = text.replace("r'\n" + "u'", "r'\\nu'")
text = text.replace("r'\n" + "otin'", "r'\\notin'")
text = text.replace("r'\n" + "eq'", "r'\\neq'")
text = text.replace("r'\n" + "abla'", "r'\\nabla'")

# And any others? Let's check the previous view
# r'\n' + 'u' -> \nu
# r'\n' + 'otin' -> \notin
# r'\n' + 'eq' -> \neq
# r'\n' + 'abla' -> \nabla

# Wait, the view showed:
# 40:             r'
# 41: u': 'ν'
# This is r'\n' + 'u'

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
