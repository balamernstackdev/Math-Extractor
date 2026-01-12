import os
import re

path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_method = [
    '    def _parse_token(self, token: str) -> Optional[ASTNode]:\n',
    '        """Convert a single token string into an ASTNode."""\n',
    '        if not token:\n',
    '            return None\n',
    '            \n',
    '        # Binomial\n',
    '        if token.startswith(r"\\binom"):\n',
    '             match = re.match(self.binomial_pattern, token)\n',
    '             if match:\n',
    '                 top = match.group(1)\n',
    '                 bottom = match.group(2)\n',
    '                 return ASTNode(node_type="binomial", children=[\n',
    '                     self._parse_expression(top),\n',
    '                     self._parse_expression(bottom)\n',
    '                 ])\n',
    '\n',
    '        # Accents\n',
    '        for cmd, sym in self.accent_commands.items():\n',
    '            if token.startswith(cmd):\n',
    '                # Extract content\n',
    '                idx = token.find("{")\n',
    '                content = token[idx+1:-1]\n',
    '                # Map to overscript semantic node\n',
    '                return ASTNode(node_type="overscript", children=[\n',
    '                    self._parse_expression(content),\n',
    '                    ASTNode(node_type="symbol", value=sym)\n',
    '                ], attributes={"accent": "true"})\n',
    '\n',
    '        # Fraction\n',
    '        if token.startswith(r"\\frac"):\n',
    '            return self._parse_fraction(token)\n',
    '            \n',
    '        # Sqrt\n',
    '        if token.startswith(r"\\sqrt"):\n',
    '            return self._parse_sqrt(token)\n',
    '            \n',
    '        # Stackrel\n',
    '        if token.startswith(r"\\stackrel"):\n',
    '             match = re.match(r"\\\\stackrel\\{([^{}]*)\\}\\{([^{}]*)\\}", token)\n',
    '             if match:\n',
    '                 top = match.group(1)\n',
    '                 bottom = match.group(2)\n',
    '                 # Treat as overscript\n',
    '                 return ASTNode(node_type="overscript", children=[\n',
    '                     self._parse_expression(bottom),\n',
    '                     self._parse_expression(top)\n',
    '                 ])\n',
    '                 \n',
    '        # Environment (Cases / Matrix / Align / Gather)\n',
    '        if token.startswith(r"\\begin"):\n',
    '             # Extract environment name\n',
    '             match = re.search(r"\\\\begin\\{([^}]+)\\}", token)\n',
    '             if match:\n',
    '                 env_name = match.group(1)\n',
    '                 # Get content between begin and end\n',
    '                 content_start = token.find("}") + 1\n',
    '                 content_end = token.rfind(r"\\end")\n',
    '                 content = token[content_start:content_end]\n',
    '\n',
    '                 matrix_node = self._parse_expression(content)\n',
    '                 \n',
    '                 # Environment mapping\n',
    '                 env_list = ["pmatrix", "bmatrix", "vmatrix", "Vmatrix", "Bmatrix", "matrix", "cases", "aligned", \n',
    '                             "align", "align*", "split", "gather", "gather*", "multline", "multline*", "tabular"]\n',
    '                 \n',
    '                 if env_name in env_list:\n',
    '                      if matrix_node.node_type != "mtable":\n',
    '                           # Wrap single row into table\n',
    '                           wrapped_row = ASTNode(node_type="mtr", children=matrix_node.children if matrix_node.children else [])\n',
    '                           matrix_node = ASTNode(node_type="mtable", children=[wrapped_row])\n',
    '                      \n',
    '                      # Fence mappings\n',
    '                      fence_map = {\n',
    '                          "pmatrix": ("(", ")"),\n',
    '                          "bmatrix": ("[", "]"),\n',
    '                          "vmatrix": ("|", "|"),\n',
    '                          "Vmatrix": ("‖", "‖"),\n',
    '                          "Bmatrix": ("{", "}"),\n',
    '                          "cases": ("{", ""),\n',
    '                      }\n',
    '                      \n',
    '                      if env_name in fence_map:\n',
    '                          opener, closer = fence_map[env_name]\n',
    '                          matrix_node.attributes["fence"] = opener\n',
    '                          matrix_node.attributes["close_fence"] = closer\n',
    '                      \n',
    '                      if env_name in ["cases", "aligned", "align", "align*", "split"]:\n',
    '                          # Ensure alignment heuristics from _parse_expression are preserved\n',
    '                          if "columnalign" not in matrix_node.attributes or matrix_node.attributes["columnalign"] == "left":\n',
    '                               matrix_node.attributes["columnalign"] = "left"\n',
    '                      \n',
    '                      # Premium Spacing Defaults\n',
    '                      matrix_node.attributes["rowspacing"] = "0.5ex"\n',
    '                      matrix_node.attributes["columnspacing"] = "1em"\n',
    '                      \n',
    '                      return matrix_node\n',
    '                      \n',
    '                 return matrix_node\n',
    '\n',
    '        # Tag support (\\tag{1.1})\n',
    '        if token.startswith(r"\\tag"):\n',
    '             content = self._extract_braced_content(token[4:])\n',
    '             return ASTNode(node_type="tag", value=content)\n',
    '        \n',
    '        # Text/Styles\n',
    '        if token.startswith("\\\\") and "{" in token and token.endswith("}"):\n',
    '             # Extract command and content\n',
    '             idx = token.find("{")\n',
    '             cmd = token[:idx]\n',
    '             content = token[idx+1:-1]\n',
    '             \n',
    '             if cmd in [r"\\text", r"\\mbox", r"\\mathrm", r"\\mathbf", r"\\mathcal", r"\\mathbb", r"\\operatorname"]:\n',
    '                 return ASTNode(node_type="text", value=content, attributes={"variant": cmd[1:]})\n',
    '        \n',
    '        # Subscript\n',
    '        if token.startswith("_"):\n',
    '             content = self._extract_braced_content(token[1:])\n',
    '             return ASTNode(node_type="subscript", children=[self._parse_expression(content)])\n',
    '             \n',
    '        # Superscript\n',
    '        if token.startswith("^"):\n',
    '             content = self._extract_braced_content(token[1:])\n',
    '             return ASTNode(node_type="superscript", children=[self._parse_expression(content)])\n',
    '             \n',
    '        # Symbol/Operator\n',
    '        return ASTNode(node_type="symbol", value=token)\n'
]

# Find start and end of _parse_token
start_line = -1
end_line = -1
for i, line in enumerate(lines):
    if 'def _parse_token' in line:
        start_line = i
    if start_line != -1 and 'def parse(' in line:
        end_line = i
        break

if start_line != -1 and end_line != -1:
    lines[start_line:end_line] = new_method

# Also fix the symbol map while we're at it (just in case)
content = "".join(lines)
# Standardize common breakages
content = content.replace("r'\\n" + "u'", "r'\\nu'")
content = content.replace("r'\\n" + "otin'", "r'\\notin'")
content = content.replace("r'\\n" + "eq'", "r'\\neq'")
content = content.replace("r'\\n" + "abla'", "r'\\nabla'")
content = content.replace("r'\\n" + "exists'", "r'\\nexists'")
content = content.replace("r'\\n" + "eg'", "r'\\neg'")
content = content.replace("r'\\n" + "olimits'", "r'\\nolimits'")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
