# Rendering Architecture & Redesign Specification

## 1. Rendering Requirements

### Inline vs Block Equations
*   **Preview Mode**: All equations in the primary preview panel must be rendered in **Block Mode** (`display="block"`).
*   **Inline Mode**: Reserved strictly for future features involving mixed text paragraphs. For now, every OCR result is treated as a distinct block element.
*   **Centering**: Block equations must be horizontally centered within their container.

### Multiline Equations
*   **Structure**: Environments containing line breaks (`\\`) or alignment tabs (`&`) — such as `align`, `gather`, `cases`, `matrix` — must be rendered using MathML `<mtable>` structures.
*   **Flattening Prohibition**: A multiline equation must **never** be flattened into a single line. The rendering engine must respect the row structure defined in the AST.
*   **Alignment**:
    *   `align`/`aligned`: alternating `right` then `left` alignment for columns (`columnalign="right left..."`).
    *   `cases`: left alignment (`columnalign="left"`) with a scalable curly brace fence.
    *   `gather`: center alignment (`columnalign="center"`).
*   **Spacing**: Standard matrix row spacing (approx `1.0ex`) must be preserved.

### Typography
*   **Font Family**: `Latin Modern Math` (primary), `Cambria Math` (fallback).
*   **Base Size**: `2.5em` (approx 36px effective size) for readability.
*   **Baseline**: Equations must be baseline-aligned if appearing inline, but center-aligned in the preview card.

## 2. Preview Panel Layout Specification

### Equation Card Layout (ASCII)

```text
+---------------------------------------------------------------+
| [STATUS_BADGE]                 [Confidence: 98%] [Valid/Invalid]|
+---------------------------------------------------------------+
|                                                               |
|        (Vertical Padding: 24px)                               |
|                                                               |
|           x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}              |  <-- Centered Equation
|                                                               |
|        (Vertical Padding: 24px)                               |
|                                                               |
+---------------------------------------------------------------+
| [Raw LaTeX Source]                                            |  <-- Collapsible/Separate Panel
| [MathML Source]                                               |
+---------------------------------------------------------------+
```

### Layout Rules
1.  **Listing**: Single-item list (current architecture) or scrolling list (future). Current focus: Single active result.
2.  **Container**: A persistent, fixed-minimum-height container to prevent layout jumping ("Cumulative Layout Shift").
3.  **Scroll**: Horizontal scrollbar must appear **only** if the equation width exceeds the panel width. Vertical scroll for the page.
4.  **Highlighting**: The entire card should have a subtle border or shadow to indicate it is the active object.

## 3. Multiline Equation Handling (CRITICAL)

### Detection
*   **Trigger**: Presence of `\\` (double backslash) tokens or specific environment keywords (`cases`, `align`, `matrix`) in the `LaTeXParser` token stream.
*   **Mechanism**: The `LaTeXParser` must switch from `_parse_expression` mode to `_parse_matrix_content` mode immediately upon detection of these triggers.

### Preservation of Structure
*   **AST Node**: Must produce an `mtable` AST node, not a `row` node.
    *   `mtable`: Attributes `columnalign`, `rowspacing`.
    *   `mtr`: Represents a row (split by `\\`).
    *   `mtd`: Represents a cell (split by `&`).
*   **Alignment Logic**:
    *   If `&` is detected: Start new `mtd` node.
    *   If `\\` is detected: Close current `mtr`, start new `mtr`.

### Matrix/Cases Handling
*   **Cases**: Wrapped in `<mfenced open="{" close="" separators="">`.
*   **Matrices**: Wrapped in `<mfenced open="[" close="]">` or parens as appropriate.

## 4. MathML Rendering Engine Recommendation

### Recommendation: MathJax 3 (CHTML)
**Selected Configuration**: `input/mml` -> `output/chtml` (CommonHTML)

### Justification
*   **Vs Native (Chromium)**: Native MathML in QtWebEngine (Chromium) is improving but still lacks consistent support for complex spacing, `mlabeledtr`, and specific `columnalign` attributes required for "Mathpix-level" fidelity on all platforms (Windows/Linux).
*   **Vs MathJax SVG**: SVG is precise but harder to select text from. CHTML allows the user to treat the equation as text (selectable).
*   **Fidelity**: MathJax provides the industry-standard layout engine that most closely matches LaTeX rendering rules (Knuth's rules).

### Configuration
```javascript
window.MathJax = {
  loader: {load: ['input/mml', 'output/chtml']},
  chtml: {
    scale: 1,                      // Global scaling
    displayAlign: 'center',        // Default alignment
    fontURL: '...'                 // Local font resources if needed
  }
};
```

## 5. Rendering Validation Rules

### Detection of Failure
1.  **Javascript Bridge**: The Preview Controller must inject a JS script that queries `MathJax.typesetPromise()` status.
2.  **DOM Check**: Check for `mjx-container.mjx-error` or specific error classes.
3.  **Size Sanity**: If `document.body.scrollHeight < 10px`, rendering essentially failed (blank).

### Fallback Strategy
**If MathML Rendering Fails:**
1.  **Mark**: Status = `INVALID_RENDER`.
2.  **Display**: Show Raw LaTeX in a `monospace` block with a "Rendering Failed" warning.
3.  **Do Not**: Show broken symbols or overlapping text.

## 6. Preview Panel Data Contract

The `PreviewController` feeds the View with:

```json
{
  "equation_id": "uuid-string",
  "render_type": "block",
  "is_multiline": true,
  "structure_type": "align", // align | cases | matrix | standard
  "content": {
    "latex": "\\begin{align}...\n...",
    "mathml": "<math display='block' xmlns='...'>...</math>",
    "ast_tree": { "type": "mtable", "children": [...] }
  },
  "metadata": {
    "confidence_score": 0.98,
    "is_valid": true,
    "error_message": null
  }
}
```

## 7. Comparison With Mathpix Preview

| Feature | Mathpix | Current Implementation | Target Redesign |
| :--- | :--- | :--- | :--- |
| **Multiline** | Perfectly aligned columns. | Often flattens to one line. | `mtable` with precise alignment. |
| **Font** | Custom Serif (Times-like). | Mixed / Sans-serif sometimes. | **Latin Modern Math**. |
| **Selection** | Equation is selectable text. | Often image or static. | **Selectable CHTML**. |
| **Error UI** | Red underline/box. | Sometimes rendering garbage. | **Explicit Error State**. |

## 8. Final Engineering Directive

### What Must Be Rewritten
1.  **`LaTeXParser.py`**:
    *   **Rewrite**: `_parse_expression` to strictly detect environments/newlines and route to `_parse_matrix_content`.
    *   **New**: `_parse_matrix_content` to handle `\\` and `&` splitting reliably.
2.  **`ASTToMathML.py`**:
    *   **Update**: `_serialize_node` to handle `mtable`, `mtr`, `mtd` types explicitly.
    *   **Update**: Add attributes for alignment (`columnalign`).
3.  **`PreviewController.py`**:
    *   **Configuration**: hardcode the robust MathJax CHTML config.
    *   **HTML Template**: alignment with Section 2 layout.

### Source of Truth
*   **Validation**: The `AST` structure is the source of truth. If the AST says "matrix", the MathML **must** be `<mtable>`.
*   **Rendering**: MathJax CHTML output is the visual source of truth.

**Implementation Priority**:
1.  Fix Parser (AST handling of multiline).
2.  Fix Serializer (MathML generation for `mtable`).
3.  Update Preview HTML/JS config.
