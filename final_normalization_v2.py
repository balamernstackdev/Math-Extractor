import os
import re

path = r'd:\test-r&d\mathpix_clone\services\ocr\latex_parser.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Standardize symbols in __init__ using \u escapes
# ∑ = \u2211, ∫ = \u222b, → = \u2192
text = text.replace("'∑'", "'\\u2211'").replace("'∏'", "'\\u220f'")
text = text.replace("'∫'", "'\\u222b'").replace("'∬'", "'\\u222c'").replace("'∭'", "'\\u222d'").replace("'∮'", "'\\u222e'")
text = text.replace("'→'", "'\\u2192'")

# 2. Fix the symbol map and large operators
# We'll do this carefully. 
# Search for the large_operators definition
large_ops_pattern = r"self.large_operators = \{.*?\}"
new_large_ops = "self.large_operators = {'\\u2211', '\\u220f', '\\u222b', '\\u222c', '\\u222d', '\\u222e', '\\u22c3', '\\u22c2', '\\u22c1', '\\u22c0', '\\\\lim', '\\\\max', '\\\\min', '\\\\sup', '\\\\inf'}"
text = re.sub(large_ops_pattern, new_large_ops, text)

# 3. Fix _parse_token implementation
# We'll use a very safe version here.
lines = text.splitlines()
start_line = -1
end_line = -1
for i, line in enumerate(lines):
    if 'def _parse_token' in line:
        start_line = i
    if start_line != -1 and 'def _parse_fraction' in line:
        end_line = i
        break

if start_line != -1 and end_line != -1:
    new_parse_token = [
        '    def _parse_token(self, token: str) -> Optional[ASTNode]:\n',
        '        """Convert a single token string into an ASTNode."""\n',
        '        if not token:\n',
        '            return None\n',
        '            \n',
        '        # Binomial\n',
        '        if token.startswith("\\\\binom"):\n',
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
        '                if idx != -1:\n',
        '                    content = token[idx+1:-1]\n',
        '                    return ASTNode(node_type="overscript", children=[\n',
        '                        self._parse_expression(content),\n',
        '                        ASTNode(node_type="symbol", value=sym)\n',
        '                    ], attributes={"accent": "true"})\n',
        '\n',
        '        # Fraction\n',
        '        if token.startswith("\\\\frac"):\n',
        '            return self._parse_fraction(token)\n',
        '            \n',
        '        # Sqrt\n',
        '        if token.startswith("\\\\sqrt"):\n',
        '            return self._parse_sqrt(token)\n',
        '            \n',
        '        # Stackrel\n',
        '        if token.startswith("\\\\stackrel"):\n',
        '             match = re.match(r"\\\\stackrel\\{([^{}]*)\\}\\{([^{}]*)\\}", token)\n',
        '             if match:\n',
        '                 top = match.group(1)\n',
        '                 bottom = match.group(2)\n',
        '                 return ASTNode(node_type="overscript", children=[\n',
        '                     self._parse_expression(bottom),\n',
        '                     self._parse_expression(top)\n',
        '                 ])\n',
        '                 \n',
        '        # Environment\n',
        '        if token.startswith("\\\\begin"):\n',
        '             match = re.search(r"\\\\begin\\{([^}]+)\\}", token)\n',
        '             if match:\n',
        '                 env_name = match.group(1)\n',
        '                 content_start = token.find("}") + 1\n',
        '                 content_end = token.rfind(r"\\\\end")\n',
        '                 content = token[content_start:content_end]\n',
        '                 matrix_node = self._parse_expression(content)\n',
        '                 \n',
        '                 env_list = ["pmatrix", "bmatrix", "vmatrix", "Vmatrix", "Bmatrix", "matrix", "cases", "aligned", \n',
        '                             "align", "align*", "split", "gather", "gather*", "multline", "multline*", "tabular"]\n',
        '                 \n',
        '                 if env_name in env_list:\n',
        '                      if matrix_node.node_type != "mtable":\n',
        '                           wrapped_row = ASTNode(node_type="mtr", children=matrix_node.children if matrix_node.children else [])\n',
        '                           matrix_node = ASTNode(node_type="mtable", children=[wrapped_row])\n',
        '                      \n',
        '                      fence_map = {"pmatrix":("(",")"), "bmatrix":("[","]"), "vmatrix":("|","|"), "Vmatrix":("‖","‖"), "Bmatrix":("{","}"), "cases":("{","")}\n',
        '                      if env_name in fence_map:\n',
        '                          matrix_node.attributes["fence"], matrix_node.attributes["close_fence"] = fence_map[env_name]\n',
        '                      \n',
        '                      if env_name in ["cases", "aligned", "split"]:\n',
        '                           matrix_node.attributes["columnalign"] = "left"\n',
        '                      \n',
        '                      matrix_node.attributes["rowspacing"], matrix_node.attributes["columnspacing"] = "0.5ex", "1em"\n',
        '                      return matrix_node\n',
        '                 return matrix_node\n',
        '\n',
        '        # Tag\n',
        '        if token.startswith("\\\\tag"):\n',
        '             content = self._extract_braced_content(token[4:])\n',
        '             return ASTNode(node_type="tag", value=content)\n',
        '        \n',
        '        # Text/Styles\n',
        '        if token.startswith("\\\\") and "{" in token and token.endswith("}"):\n',
        '             idx = token.find("{")\n',
        '             cmd = token[:idx]\n',
        '             content = token[idx+1:-1]\n',
        '             if cmd in ["\\\\text", "\\\\mbox", "\\\\mathrm", "\\\\mathbf", "\\\\mathcal", "\\\\mathbb", "\\\\operatorname"]:\n',
        '                 return ASTNode(node_type="text", value=content, attributes={"variant": cmd[1:]})\n',
        '        \n',
        '        # Sub/Sup\n',
        '        if token.startswith("_"):\n',
        '             return ASTNode(node_type="subscript", children=[self._parse_expression(self._extract_braced_content(token[1:]))])\n',
        '        if token.startswith("^"):\n',
        '             return ASTNode(node_type="superscript", children=[self._parse_expression(self._extract_braced_content(token[1:]))])\n',
        '             \n',
        '        # Symbol\n',
        '        if token in self.symbol_map:\n',
        '             return ASTNode(node_type="symbol", value=self.symbol_map[token])\n',
        '        return ASTNode(node_type="symbol", value=token)\n'
    ]
    lines[start_line:end_line] = new_parse_token

# 4. Final symbol map cleanup for Summation
content = "\n".join(lines)
content = content.replace("r'\\\\sum': '\\u2211'", "r'\\\\sum': '\\u2211'") # Ensure it's there

with open(parser_path, 'w', encoding='utf-8') as f:
    f.write(content)
