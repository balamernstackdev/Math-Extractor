# services/ocr/latex_structures.py
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from latex2mathml.converter import convert as latex2mathml
from core.logger import logger

ET.register_namespace("", "http://www.w3.org/1998/Math/MathML")


class LatexStructures:
    """Multiline and matrix MathML builders."""

    # -------------------------------
    # MULTILINE
    # -------------------------------
    def convert_multiline(self, latex: str) -> str:
        parsed = self._parse_multiline(latex)
        if not parsed:
            raise ValueError("Not multiline")

        env, rows = parsed

        math = ET.Element("math", xmlns="http://www.w3.org/1998/Math/MathML", display="block")
        mtable = ET.SubElement(math, "mtable")

        if env == "aligned":
            mtable.set("columnalign", "right left")
        if env == "cases":
            mtable.set("columnalign", "left left")

        for row in rows:
            mtr = ET.SubElement(mtable, "mtr")
            for cell in row:
                mtd = ET.SubElement(mtr, "mtd")
                try:
                    root = ET.fromstring(latex2mathml(cell))
                    for ch in list(root):
                        mtd.append(ch)
                except Exception:
                    mi = ET.SubElement(mtd, "mi")
                    mi.text = "⋯"

        return ET.tostring(math, encoding="unicode")

    def _parse_multiline(self, latex: str):
        m = re.search(r'\\begin\{(aligned|cases|array)\}', latex)
        if not m:
            return None

        env = m.group(1)
        body = re.search(rf'\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}', latex, re.DOTALL)
        if not body:
            raise ValueError("Truncated multiline env")

        rows = []
        for r in re.split(r'\\\\', body.group(1)):
            r = r.strip()
            if not r:
                continue
            rows.append([c.strip() for c in r.split("&")])

        return env, rows

    # -------------------------------
    # MATRIX
    # -------------------------------
    def convert_matrix(self, matrix: list[list[str]]) -> str:
        math = ET.Element("math", xmlns="http://www.w3.org/1998/Math/MathML", display="block")
        mfenced = ET.SubElement(math, "mfenced", open="[", close="]")
        mtable = ET.SubElement(mfenced, "mtable")

        for row in matrix:
            mtr = ET.SubElement(mtable, "mtr")
            for cell in row:
                mtd = ET.SubElement(mtr, "mtd")
                try:
                    root = ET.fromstring(latex2mathml(cell))
                    for ch in list(root):
                        mtd.append(ch)
                except Exception:
                    mi = ET.SubElement(mtd, "mi")
                    mi.text = "⋯"

        return ET.tostring(math, encoding="unicode")
