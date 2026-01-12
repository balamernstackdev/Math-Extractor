# PDF Viewer UX Design - Mathpix-Clone

## 1. PDF Viewer Layout

**Philosophy:** Content-first, minimal distraction, maximum utility.

```text
+-----------------------------------------------------------------------------------------------+
|  [Toolbar: Tools | Zoom | Pagination | Search | Export ]                                    |
+------+-------------------------------------------------------+--------------------------------+
| THUMB|                                                       |                                |
| NAILS|                                                       |                                |
|      |                                                       |                                |
| [P1] |              PDF CANVAS (Infinite Scroll)             |      EXTRACTION SIDEBAR        |
|      |                                                       |                                |
| [P2] |           [ Page 1 Header ........... ]               |    [ Equation #1 Preview ]     |
|      |                                                       |    [ LaTeX | MathML ]          |
| [P3] |           yp = mx + b  [ Clickable Box ]              |                                |
|      |                                                       |    [ Equation #2 Preview ]     |
| [P4] |           [ Status: Analyzed (12 found) ]             |    [ LaTeX | MathML ]          |
|      |                                                       |                                |
|      |                                                       |                                |
+------+-------------------------------------------------------+--------------------------------+
| [Status Bar: Ready | Processing Page 3... | Confidence: High ]                                |
+-----------------------------------------------------------------------------------------------+
```

*   **Left Panel (Navigation):** Vertically scrollable list of page thumbnails. Current viewing page highlighted.
*   **Center Panel (Canvas):** High-performance PDF rendering surface. Infinite scroll enabled.
*   **Right Panel (Inspector):** Context-aware panel. When nothing selected, shows list of extracted items for current page. When item selected, shows detailed `PreviewPanel`.
*   **Floating Controls:** Minimal floating HUD for quick zoom level interaction at bottom-center of canvas.

## 2. Page-Level & Region-Level UX

**Interaction Model:** "See, Hover, Click".

*   **Visual Discovery:**
    *   As pages load, detected math regions appear as subtle **overlay boxes**.
    *   **State:** `Dashed Gray` (Scanning) → `Solid Blue` (Detected) → `Solid Green` (Processed).
*   **Hover Effect:**
    *   Hovering a math region highlights it with a `Glow Effect` and changes cursor to `Pointer`.
    *   Tooltip appears: "Click to Extract".
*   **Selection:**
    *   **Single Click:** Instantly scrolls Right Panel to the corresponding result.
    *   **Double Click:** Opens "Focus Mode" (popup) for just that equation.
    *   **Marquee Tool:** User can drag-select a custom region if auto-detection missed something.
*   **Navigation:**
    *   Scrolling updates the "Current Page" indicator.
    *   Clicking a thumbnail jumps instantly.
    *   Arrow keys navigate pages.

## 3. Extraction Progress & Status UX

**Goal:** Eliminate anxiety. Show work happening.

*   **Page Status Indicators:**
    *   Each thumbnail has a small status dot: `Gray` (Pending), `Blue Pulse` (Processing), `Green Check` (Done), `Red Exclamation` (Failed).
*   **Canvas Overlay:**
    *   While processing a page, a thin, non-blocking progress bar appears at the top of that specific page's container.
    *   detected regions fade in progressively (Skeleton Loading -> Real Box).
*   **Global Status:**
    *   Bottom status bar: "Processed 5/12 pages. 45 Equations found."

## 4. Equation Interaction UX

**Goal:** Trust and Speed.

*   **Confident Display:**
    *   Extracted equations are rendered beautifully using MathJax/KaTeX in the sidebar.
    *   **Confidence Badge:** Color-coded pill (95% Green, <70% Orange).
*   **Actions:**
    *   **One-Click Copy:** "Copy LaTeX", "Copy MathML", "Copy Image" icons visible on hover.
    *   **Quick Edit:** Hovering an equation reveals an "Edit" pencil icon.
*   **Feedback Loop:**
    *   If output is wrong, user clicks "Report/Fix" which switches to "Scribble/Correction Mode" (drawing on the original region).

## 5. Loading & Perceived Performance UX

**Strategy:** Optimistic UI.

*   **Immediate Feedback:**
    *   PDF Upload -> Instant transition to Viewer.
    *   Show blurred low-res text immediately while high-res renders.
*   **Skeleton States:**
    *   Right sidebar shows "Skeleton Text" blocks while OCR runs.
    *   Prevent interface jumping/layout shifts.
*   **Non-Blocking:**
    *   OCR runs in a background thread. The UI **never** freezes.
    *   User can read Page 1 while Page 50 is processing.

## 6. Toolbar & Controls Design

**Clean and Contextual.**

*   **Primary (Left):**
    *   [Icon] Sidebar Toggle
    *   [Icon] Selection Tool (Arrow) vs. Crop Tool (Crosshair)
*   **Center (Pagination):**
    *   `[ < ]  Page 5 / 24  [ > ]` (Input field editable)
*   **Right (View Options):**
    *   `-  100%  +` (Zoom)
    *   [Fit Width] / [Fit Page]
    *   [Export All] (Dropdown: Export to Word, Markdown, LaTeX)
*   **Hidden (Context Menu):** Right-click on PDF background provides "Rotate Page", "Rescan Page".

## 7. Error & Recovery UX

**Fail Gracefully.**

*   **Page Failure:**
    *   If a page fails OCR: show a gentle "Retry" button overlay on that page ONLY. Do not crash the app.
    *   Thumbnail shows amber warning.
*   **Low Confidence:**
    *   Regions with low OCR confidence are highlighted in `Orange`.
    *   Sidebar prompts: "Please verify accuracy".
*   **Partial Extraction:**
    *   Show what we got. Don't hide partial results.

## 8. UX Performance Targets

*   **Time to First Paint:** < 100ms (Viewer frame appears).
*   **PDF text readable:** < 500ms.
*   **First Equation ROI appearing:** < 1s.
*   **Equation Selection Latency:** < 50ms (Instant feeling).
*   **Scroll smoothness:** 60fps (Mandatory).

**Mathpix Superiority Note:** Mathpix excels at "Snip to Solution" speed. To match this, our "Crop Tool" must be instant—drag, release, and the result is *already* loading in the sidebar. No extra "Confirm" clicks.
