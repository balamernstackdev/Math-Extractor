import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix environment return indents
for i, line in enumerate(lines):
    if i == 466: # Line 467
        lines[i] = '                       return matrix_node\n'
    if i == 467: # Line 468
        lines[i] = '                  return matrix_node\n'
    if i == 470: # Line 471 (\tag)
        lines[i] = '         if token.startswith(r"\\\\tag"):\n' # No, wait. 

# Actually, I'll just use the view_code_item output as a reference.
# I will use a very simple replace.
content = "".join(lines)
content = content.replace('      \n              return matrix_node', '\n             return matrix_node')
# ...

# Better yet, I'll just rewrite _parse_token again, but this time VERY carefully.
pass
