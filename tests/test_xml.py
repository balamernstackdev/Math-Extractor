"""Tests for XML writer."""
from __future__ import annotations

from services.exporters.xml_writer import XMLWriter


def test_xml_writer(tmp_path) -> None:
    writer = XMLWriter()
    writer.output_path = tmp_path / "eq.xml"
    path = writer.write_document([{"id": "eq1", "latex": "x", "mathml": "<mrow/>"}])
    assert path.exists()

