"""XML writer for equations."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from core.config import settings
from core.logger import logger
from utils.xml_utils import prettify_xml


class XMLWriter:
    """Persist equations and metadata to XML."""

    def __init__(self) -> None:
        self.output_path = settings.data_dir / "equations.xml"
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def write_document(self, equations: Iterable[dict[str, object]]) -> Path:
        """Write equations to XML file."""
        logger.info("Writing XML to %s", self.output_path)
        root = ET.Element("equations")
        for eq in equations:
            equation = ET.SubElement(root, "equation", id=str(eq.get("id", "")))
            ET.SubElement(equation, "latex").text = str(eq.get("latex", ""))
            ET.SubElement(equation, "mathml").text = str(eq.get("mathml", ""))
            bbox = ET.SubElement(equation, "bounding_box")
            bbox.set("x", str(eq.get("x", "")))
            bbox.set("y", str(eq.get("y", "")))
            bbox.set("w", str(eq.get("w", "")))
            bbox.set("h", str(eq.get("h", "")))

        xml_str = prettify_xml(root)
        self.output_path.write_text(xml_str, encoding="utf-8")
        return self.output_path

