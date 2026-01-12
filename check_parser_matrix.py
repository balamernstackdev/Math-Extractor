
from services.ocr.latex_parser import LaTeXParser
import sys

def check_matrix():
    parser = LaTeXParser()
    latex = r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}"
    print(f"Parsing: {latex}")
    try:
        ast = parser.parse(latex)
        print(ast)
        # Manually inspect children to see structure
        if ast.node_type == 'matrix':
            print(f"Matrix children count: {len(ast.children)}")
            for i, child in enumerate(ast.children):
                print(f"  Child {i}: {child.node_type} (children: {len(child.children)})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_matrix()
