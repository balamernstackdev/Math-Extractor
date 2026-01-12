"""
HTML Exporter Service
Handles conversion of PDF documents to semantic HTML with MathML.
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from core.logger import logger
from services.ocr.formula_detector import FormulaDetector


import fitz  # PyMuPDF
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from core.logger import logger
from services.ocr.formula_detector import FormulaDetector
from services.ocr.image_to_latex import ImageToLatex
from services.ocr.latex_to_mathml import LatexToMathML

class LayoutBlock:
    """Represents a structural block of content (text or potential math)."""
    def __init__(self, bbox: Tuple[float, float, float, float], text: str = "", block_type: str = "text", mathml: str = ""):
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.text = text
        self.type = block_type  # 'text', 'math', 'header', 'footer'
        self.mathml = mathml

class PDFToHTMLConverter:
    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
            
        self.doc = fitz.open(self.pdf_path)
        self.formula_detector = FormulaDetector()
        self.latex_ocr = ImageToLatex()
        self.latex_to_mathml = LatexToMathML()
        self.temp_dir = Path("temp_processing")
        self.temp_dir.mkdir(exist_ok=True)
        
    def convert(self, max_pages: Optional[int] = None, progress_callback=None) -> str:
        """Execute full conversion pipeline."""
        logger.info(f"Starting PDF to HTML conversion for: {self.pdf_path.name}")
        
        html_pages = []
        total_pages = len(self.doc)
        if max_pages:
            total_pages = min(total_pages, max_pages)
            
        for page_num, page in enumerate(self.doc):
            if max_pages and page_num >= max_pages:
                break
            
            msg = f"Processing page {page_num + 1}/{total_pages}..."
            logger.debug(msg)
            if progress_callback:
                progress_callback(msg)
                
            page_content = self._process_page(page, page_num)
            html_pages.append(page_content)
            
        # Cleanup
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")

        return self._assemble_html(html_pages)
        
    def _process_page(self, page: fitz.Page, page_num: int) -> str:
        """Process a single page: extract layout, detect math, merge."""
        
        # 1. Render page for visual detection
        pix = page.get_pixmap(dpi=300)
        temp_img_path = self.temp_dir / f"page_{page_num}.png"
        pix.save(str(temp_img_path))
        
        # 2. Math Detection (Visual)
        # Get math blocks with point coordinates
        math_blocks = self._detect_math_regions(page, temp_img_path, pix.width, pix.height)
        
        # 3. Text Extraction (Layout)
        # flags: Preserve whitespace, ligatures, etc.
        text_page = page.get_text("dict", flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)
        raw_blocks = text_page["blocks"]
        
        # 4. Merge Content
        # We need to filter out text blocks that overlap with math blocks
        final_blocks = self._merge_content(raw_blocks, math_blocks)
        
        # 5. Generate HTML for this page
        page_html = f'<div class="page" id="page-{page_num+1}">\n'
        
        # Sort blocks by Y then X to maintain reading order roughly
        final_blocks.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
        
        for block in final_blocks:
            if block.type == "math":
                page_html += self._math_block_to_html(block)
            elif block.type == "image":
                page_html += self._image_block_to_html(block)
            else:
                page_html += self._text_block_to_html(block)
                 
        page_html += '</div>'
        return page_html

    def _detect_math_regions(self, page, img_path: Path, img_w: int, img_h: int) -> List[LayoutBlock]:
        """Detect math, run OCR, and return math blocks."""
        detected_boxes = self.formula_detector.detect_formulas(img_path)
        
        scale_x = page.rect.width / img_w
        scale_y = page.rect.height / img_h
        
        math_blocks = []
        for box in detected_boxes:
            # bbox in pixels
            x, y, w, h = box['x'], box['y'], box['w'], box['h']
            
            # Crop image for OCR
            # We can use the cached image at img_path or re-crop
            # For simplicity using existing ImageToLatex which might handle cropping or we pass the crop
            # ImageToLatex usually takes a path. We can crop the region from the temp image.
            
            # Convert to Points for layout matching
            x0 = x * scale_x
            y0 = y * scale_y
            x1 = (x + w) * scale_x
            y1 = (y + h) * scale_y
            
            # Run OCR
            # Ideally we pass the crop. Let's do a quick crop here.
            # Using opencv or PILLOW would be efficient.
            # Or use ImageToLatex which might support bbox?
            # Looking at ImageToLatex, it takes an image path.
            
            # Crop and save temp snippet
            import cv2
            full_img = cv2.imread(str(img_path))
            if full_img is not None:
                roi = full_img[y:y+h, x:x+w]
                snippet_path = self.temp_dir / f"math_{x}_{y}.png"
                cv2.imwrite(str(snippet_path), roi)
                
                try:
                    latex = self.latex_ocr.image_to_latex(str(snippet_path))
                    mathml = self.latex_to_mathml.convert(latex)
                except Exception as e:
                    logger.error(f"Math conversion failed: {e}")
                    latex = ""
                    mathml = "<math><mtext>[Equation Extraction Failed]</mtext></math>"
                
                math_blocks.append(LayoutBlock(
                    bbox=(x0, y0, x1, y1),
                    text=latex,
                    block_type="math",
                    mathml=mathml
                ))
                
        return math_blocks

    def _merge_content(self, text_blocks_dict: List[dict], math_blocks: List[LayoutBlock]) -> List[LayoutBlock]:
        """Merge text, image, and math blocks, removing text that overlaps math."""
        merged = []
        
        # Add all math blocks first
        merged.extend(math_blocks)
        
        for block in text_blocks_dict:
            # Handle Image Blocks (Type 1)
            if block['type'] == 1:
                # Check overlap with detected math (sometimes math is an image)
                b_bbox = block['bbox']
                overlaps_math = False
                for mb in math_blocks:
                    if self._check_overlap(b_bbox, mb.bbox):
                        overlaps_math = True
                        break
                
                if not overlaps_math:
                    # Extract image data
                    image_data = block.get('image')
                    ext = block.get('ext', 'png')
                    if image_data:
                        import base64
                        b64_data = base64.b64encode(image_data).decode('utf-8')
                        data_uri = f"data:image/{ext};base64,{b64_data}"
                        
                        merged.append(LayoutBlock(
                            bbox=b_bbox,
                            text=data_uri, # Store URI in text field
                            block_type="image"
                        ))
                continue

            # Handle Text Blocks (Type 0)
            if block['type'] != 0: continue 
            
            # Text Block BBox
            b_bbox = block['bbox'] # x0, y0, x1, y1
            
            # Check overlap with any math block
            overlaps_math = False
            for mb in math_blocks:
                if self._check_overlap(b_bbox, mb.bbox):
                    overlaps_math = True
                    break
            
            if not overlaps_math:
                lb = LayoutBlock(bbox=b_bbox, block_type="text")
                lb.raw_data = block # Store full PyMuPDF block data
                merged.append(lb)
                
        return merged

    def _check_overlap(self, box1, box2, threshold=0.5):
        """Check if box1 overlaps box2 significantly."""
        x0_1, y0_1, x1_1, y1_1 = box1
        x0_2, y0_2, x1_2, y1_2 = box2
        
        dx = min(x1_1, x1_2) - max(x0_1, x0_2)
        dy = min(y1_1, y1_2) - max(y0_1, y0_2)
        
        if (dx >= 0) and (dy >= 0):
            intersection = dx * dy
            area1 = (x1_1 - x0_1) * (y1_1 - y0_1)
            # If intersection covers > 50% of the text block, it's an overlap
            if area1 > 0 and (intersection / area1) > threshold:
                return True
        return False

    def _text_block_to_html(self, block: LayoutBlock) -> str:
        """Convert a text LayoutBlock (with raw PyMuPDF data) to HTML."""
        if not hasattr(block, 'raw_data'): return ""
        
        html = f'<div class="text-block" style="position:absolute; top:{block.bbox[1]}pt; left:{block.bbox[0]}pt; width:{block.bbox[2]-block.bbox[0]}pt;">'
        
        for line in block.raw_data["lines"]:
            html += '<p style="margin:0;">'
            for span in line["spans"]:
                text = span["text"]
                # Escape HTML special chars using html.escape if imported, otherwise manual replace
                text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                # --- Styling ---
                styles = []
                styles.append(f"font-size:{span['size']:.1f}pt")
                
                # Check Flags (Bold=2^4, Italic=2^1)
                flags = span["flags"]
                if flags & 16: # Bold
                    styles.append("font-weight:bold")
                if flags & 2:  # Italic
                    styles.append("font-style:italic")
                
                # Color (sRGB int)
                color = span.get("color", 0)
                if color != 0: # Black is default
                    # Convert int to hex
                    hex_color = f"#{color:06x}"
                    styles.append(f"color:{hex_color}")
                
                # Font Family (Simple Heuristic for now)
                font_name = span["font"].lower()
                if "serif" in font_name:
                    styles.append("font-family:serif")
                elif "mono" in font_name or "code" in font_name:
                    styles.append("font-family:monospace")
                else:
                    styles.append("font-family:sans-serif")

                style_str = "; ".join(styles)
                html += f'<span style="{style_str}">{text}</span> '
            html += "</p>"
        html += "</div>\n"
        return html

    def _math_block_to_html(self, block: LayoutBlock) -> str:
        """Convert a math LayoutBlock to HTML."""
        width = block.bbox[2] - block.bbox[0]
        height = block.bbox[3] - block.bbox[1]
        
        return f"""
        <div class="math-block" style="position:absolute; top:{block.bbox[1]}pt; left:{block.bbox[0]}pt; width:{width}pt; height:{height}pt; display:flex; align-items:center; justify-content:center;">
            {block.mathml}
        </div>
        """

    def _image_block_to_html(self, block: LayoutBlock) -> str:
        """Convert an image LayoutBlock to HTML."""
        width = block.bbox[2] - block.bbox[0]
        height = block.bbox[3] - block.bbox[1]
        
        return f"""
        <div class="image-block" style="position:absolute; top:{block.bbox[1]}pt; left:{block.bbox[0]}pt; width:{width}pt; height:{height}pt;">
            <img src="{block.text}" style="width:100%; height:100%; object-fit:contain;" />
        </div>
        """

    def _assemble_html(self, pages: List[str]) -> str:
        """Wrap pages in standard HTML5 skeleton."""
        styles = self._get_base_styles()
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.pdf_path.name}</title>
    <style>
        {styles}
    </style>
    <!-- MathJax for rendering MathML fallback/styling -->
    <script type="text/javascript" id="MathJax-script" async
      src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js">
    </script>
</head>
<body>
    <div class="document-container">
        {''.join(pages)}
    </div>
</body>
</html>"""

    def _get_base_styles(self) -> str:
        return """
            body {
                background: #f0f2f5;
                margin: 0;
                padding: 20px;
                font-family: 'Inter', system-ui, sans-serif;
            }
            .document-container {
                max_width: 900px;
                margin: 0 auto;
                background: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                border-radius: 8px;
                overflow: hidden;
                position: relative; /* For absolute positioning context ? No, pages are relative */
            }
            .page {
                /* A4 aspect ratio approx */
                width: 595pt; 
                height: 842pt;
                position: relative; /* Absolute children position relative to page */
                margin: 0 auto 20px auto;
                background: white;
                border-bottom: 1px solid #e5e7eb;
                overflow: hidden;
            }
            .text-block {
                line-height: 1.2;
            }
            .math-block {
                /* background: rgba(37, 99, 235, 0.1); debug highlight */
            }
        """
