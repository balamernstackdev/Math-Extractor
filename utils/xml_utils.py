"""XML helper utilities."""
from __future__ import annotations

from xml.dom import minidom
from xml.etree import ElementTree as ET


def prettify_xml(element: ET.Element) -> str:
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(element, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

