# PDF → HTML + MathML Conversion Strategy

## 1. PDF → HTML Conversion Strategy

To achieve Acrobat-level fidelity while ensuring semantic math extraction, we cannot rely solely on simple text extractors. The strategy operates on a **Hybrid Layout-Analysis Pipeline**.

### text Extraction & Layout Preservation
*   **Coordinate-Based Extraction**: Use a low-level PDF parser (e.g., MuPDF or pdfplumber) to extract characters with their bounding boxes `(x0, y0, x1, y1)`, font information, and size.
*   **Reading Order Reconstruction**: Standard PDFs do not guarantee reading order. We must implement an XY-cut algorithm or topological sort based on bounding boxes to segregate headers, columns, and footers.
*   **Paragraph & Line Reconstruction**:
    *   **Line Grouping**: Group characters into lines based on vertical overlap (`y`-axis tolerance).
    *   **Paragraph Grouping**: Group lines based on leading (line-height) consistency and indentations.
*   **Font Handling**: Map PDF internal fonts (e.g., `/F1`, `/CMMI10`) to standard web-safe font stacks or embed subsetted fonts if exact replication is required.
*   **Semantic Tagging**:
    *   Detect Headers (H1-H6) via font size analysis relative to body text.
    *   Detect Lists via bullet glyph detection (•, -, 1.) at line starts.
    *   Detect Tables via ruling line intersection analysis and grid sparsity.

### Handling Structural Elements
*   **Multi-column Layouts**: Detect white-space separation channels larger than the average character width. defined columns break the linear text flow.
*   **Headers/Footers**: Identify repeating content at the top/bottom 10% of pages across the document and segregate it to `<header>`/`<footer>` tags, or remove if strictly reading-view is desired.
*   **Page Breaks**: Insert `<hr class="page-break" data-page-num="n">` markers to maintain pagination reference.

## 2. Equation Detection Strategy (CRITICAL)

Equation detection involves three sensing layers operating in parallel to ensure 99% recall.

### Layer A: Font-Based Detection (Text Layer)
*   **Math Fonts**: Scan character attributes for known mathematical font signatures (e.g., `CMMI`, `CMSY`, `MSBM`, `Euclid`, `MathJax_Math`).
*   **Unicode Ranges**: Detect high density of characters in Unicode Mathematical Operators blocks (`U+2200`–`U+22FF`), Greek (`U+0370`–`U+03FF`), and Supplemental Math blocks.
*   **Heuristics**: Isolated single characters (italicized `x`, `y`) or specific sequences (`=`, `+`, `\sum`) trigger potential inline math labeling.

### Layer B: Vector/Graphic Detection
*   **Path Analysis**: Math often involves vector paths not found in text (horizontal lines for divisions, specialized curves for integrals `∫`, square roots `√`).
*   **Clustering**: Group vector elements that are spatially close to text but are not text themselves.

### Layer C: Visual Object Detection (Hybrid)
*   **Computer Vision**: A lightweight object detection model (e.g., YOLOv8-Math) runs on the rendered page image to catch equations that are baked as bitmaps or complex structures undetectable by text/vector analysis.
*   **Masking**: Detected bounding boxes are marked as "Math Regions" and excluded from the standard text extraction flow.

### Classification: Inline vs. Block
*   **Inline**: Height matches the surrounding text line; flows horizontally.
*   **Block**: Centered, has significant vertical whitespace before/after, or is numbered (e.g., `(1.1)`).

## 3. MathML Generation Pipeline

Once a region is identified as math, it enters a dedicated subsystem.

`PDF Math Region` → `Extraction` → `Normalization` → `MathML`

1.  **Extraction**:
    *   *Path 1 (Text-Rich)*: If the region has clean unicode text (common in modern generated PDFs), extract the unicode string.
    *   *Path 2 (Vector/Image)*: Render the region to a high-DPI image (300+ DPI).
2.  **Conversion Core (OCR equivalent)**:
    *   Use an encoder-decoder model (like an optimized `Pix2Tex`) to convert the image/text representation into a **Structural AST** or Internal LaTeX representation.
    *   *Note*: While "No LaTeX exposure" is required, an internal LaTeX intermediate is industry standard for robust MathML generation because direct Image-to-MathML models often hallucinate structure.
3.  **MathML Transpilation**:
    *   Convert the AST/LaTeX to MathML using a robust parser (e.g., `LaTeXML` or a custom parser).
    *   **Namespace**: Ensure `<math xmlns="http://www.w3.org/1998/Math/MathML">`.
4.  **Validation**:
    *   Validate against the MathML 3.0 DTD.
    *   Check for "red flag" structures (empty `<mrow>`, unbalanced fences).

## 4. HTML + MathML Embedding Rules

The final output is a single HTML5 file.

*   **Doctype**: `<!DOCTYPE html>` with `UTF-8` charset.
*   **Inline Math**:
    ```html
    <p>The variable <math display="inline">...</math> denotes...</p>
    ```
*   **Block Math**:
    ```html
    <div class="math-block">
        <math display="block">...</math>
    </div>
    ```
*   **Styling**:
    *   Inject a base CSS to handle MathML font consistency (`font-family: 'Latin Modern Math', STIX Two Math, serif`).
    *   Ensure `overflow-x: auto` on math blocks for mobile responsiveness.
*   **Accessibility**:
    *   Add `aria-label` or `alttext` to the `<math>` tag containing the textual representation (e.g., LaTeX or spoken English) for screen readers.

## 5. Edge Cases & Failure Handling

*   **Corrupted Text Layer ("Tofuland")**:
    *   If extracted text contains >20% unknown glyphs (cid:X) or invalid unicode, strictly fallback to **Full Page OCR** (Tesseract/EasyOCR) for text reconstruction.
*   **Mixed Text-Math Lines**:
    *   Use the bounding box "seam carving" approach: strictly chop the text stream where the math bounding box begins and resume where it ends. Do not attempt to overlap.
*   **Split Equations**:
    *   Detect equations ending with operators (`+`, `-`, `=`) at the end of a line; attempt to merge with the subsequent line if it starts with a compatible term.
*   **Low-Quality Scans**:
    *   Pre-process with binarization and deskewing before passing to the Math OCR engine.

## 6. Accuracy & Validation Rules

*   **Text Accuracy**:
    *   Use confidence scores from the OCR/Extraction engine.
    *   *Rule*: If confidence < 80%, highlight the region in the internal QA viewer (not end user).
*   **MathML Schema**:
    *   Every generated MathML snippet must pass an XML validity check.
    *   *Auto-Recovery*: If MathML generation fails, fallback to an SVG render of the equation with a text-based `alt` tag (graceful degradation).
*   **Visual Regression**:
    *   (Dev Phase) Render the generated HTML and overlay it on the original PDF. A structural similarity index (SSIM) > 0.95 is the target.

## 7. Performance Considerations

*   **Streaming**: Do not load the entire PDF into RAM. Process page-by-page.
    *   `Page N` Input → `Page N` Worker → `Page N` HTML Fragment.
*   **Parallelization**:
    *   Text extraction is CPU bound (Parallelize by page).
    *   Math OCR is GPU/Neural bound (Batch math regions across pages).
*   **Lazy Evaluation**:
    *   Generate a skeletal HTML structure immediately.
    *   Enhance math regions asynchronously if processing time > 2s per page.

## 8. Final Recommendation

**Feasibility**: **High**.
Building a PDF → HTML + MathML converter is completely feasible using today's Vision-Language Models (VLM) for the math components and standard PDF parsers for text.

**Limitations vs. Acrobat**:
*   Acrobat uses proprietary font synthesis which is pixel-perfect. We will rely on standard web fonts, so strict typographic layout (kerning, line-breaking) will vary slightly from the PDF.
*   Complex vector diagrams containing labels will likely need to be treated as Images (SVG/PNG) rather than decomposable HTML/MathML.

**Directive**:
Implement a **Pipeline Architecture**:
1.  **Ingest**: `pymupdf` for layout \+ text detection.
2.  **Segment**: YOLO model to identify Math vs Text vs Image regions.
3.  **Process**:
    *   Text Regions -> Clean Text.
    *   Math Regions -> `Pix2Tex` (Visual) -> LaTeX -> MathML.
4.  **Synthesize**: Jinja2 Template to construct the final HTML.

This ensures strict separation of concerns and robust error recovery.
