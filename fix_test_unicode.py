import os

path = r'd:\test-r&d\mathpix_clone\tests\verify_semantic_ast.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace literals with \u escapes in the test script
text = text.replace('"∑"', "'\\u2211'").replace('"→"', "'\\u2192'")
text = text.replace('"∬"', "'\\u222c'").replace('"˙"', "'\\u02d9'")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
