"""
markdown_exporter.py
Service for batch exporting snips as a structured Markdown file.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import datetime

class MarkdownExporter:
    """Orchestrates the export of snips to Markdown."""
    
    def __init__(self):
        pass

    def export(self, records: List[Dict], output_path: Path) -> bool:
        """
        Export a list of snip records to a markdown file.
        
        Args:
            records: List of snip records from SnipRepository.
            output_path: Path where to save the .md file.
        """
        try:
            content = []
            content.append(f"# Mathpix Clone - Batch Export")
            content.append(f"Exported on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content.append(f"Total Snips: {len(records)}")
            content.append("\n---\n")

            for idx, record in enumerate(records, 1):
                latex = record.get("latex", "")
                created_at = record.get("created_at", 0)
                date_str = datetime.datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")
                
                content.append(f"## Snip {idx} ({date_str})")
                content.append("\n**LaTeX:**")
                content.append(f"```latex\n{latex}\n```")
                content.append("\n**Rendered:**")
                # Inline rendering hint for markdown readers
                content.append(f"$${latex}$$")
                
                image_path = record.get("image")
                if image_path and Path(image_path).exists():
                    # We use relative path if possible, or just absolute for local use
                    content.append(f"\n**Original Image:**\n![Snip {idx}]({Path(image_path).as_uri()})")
                
                content.append("\n---\n")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(content))
            
            return True
        except Exception as e:
            from core.logger import logger
            logger.error(f"[MarkdownExporter] Export failed: {e}")
            return False
