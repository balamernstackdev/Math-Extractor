import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Fix the literal \n issue
# The lines were joined with literal '\n' characters in the previous run
# and I might have literal newline characters too.
# Let's split by literal '\n' backslash-n
lines = text.split('\\n')
new_text = '\n'.join(lines)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)
