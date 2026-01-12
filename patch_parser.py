import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Expand environment list
old_env = 'if env_name in ["pmatrix", "bmatrix", "vmatrix", "Vmatrix", "Bmatrix", "matrix", "cases", "aligned"]:'
new_env = 'if env_name in ["pmatrix", "bmatrix", "vmatrix", "Vmatrix", "Bmatrix", "matrix", "cases", "aligned", "align", "align*", "split", "gather", "gather*", "multline", "multline*", "tabular"]:'
content = content.replace(old_env, new_env)

# Update align support
old_align = 'if env_name in ["cases", "aligned"]:'
new_align = 'if env_name in ["cases", "aligned", "align", "align*", "split"]:'
content = content.replace(old_align, new_align)

# Add \tag support
tag_prev = 'return matrix_node'
tag_insert = '''return matrix_node
         
         # Tag support (\\tag{1.1})
         if token.startswith(r'\\tag'):
              content = self._extract_braced_content(token[4:])
              return ASTNode(node_type="tag", value=content)'''

# We need to be careful with replace for 'return matrix_node' as there are multiple.
# The one we want is at the end of the begin block.
# It's at line 470.
lines = content.splitlines()
for i, line in enumerate(lines):
    if 'return matrix_node' in line and i > 460 and i < 480:
        lines[i] = tag_insert
        break

with open(path, 'w', encoding='utf-8') as f:
    f.write('\\n'.join(lines))
