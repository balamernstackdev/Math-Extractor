import os
path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    stripped = line.strip()
    if stripped == 'return matrix_node' and line.startswith('return'):
        # This is the line 477
        new_lines.append('             return matrix_node\n')
    elif stripped == '# Tag support (\\tag{1.1})':
        new_lines.append('    # Tag support (\\tag{1.1})\n')
    elif stripped == "if token.startswith(r'\\tag'):":
        new_lines.append("    if token.startswith(r'\\tag'):\n")
    elif stripped == 'content = self._extract_braced_content(token[4:])':
        new_lines.append('         content = self._extract_braced_content(token[4:])\n')
    elif stripped == 'return ASTNode(node_type="tag", value=content)':
        new_lines.append('         return ASTNode(node_type="tag", value=content)\n')
    elif stripped == 'return matrix_node' and line.startswith('                  return'):
        # Remove this extra return
        continue
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
